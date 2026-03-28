"""CircuitVerse generation via Yosys synthesis.

Supports two axes (combinable):
  flatten=True    — single flattened scope (default)
  flatten=False   — preserve module hierarchy (SubCircuit scopes)
  gate_level=True — decompose to 1-bit primitives (AND/OR/NOT/DFF/MUX)
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

_log: logging.Logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from synthesis.hierarchical.scope_cache import ScopeCache

from common.node_alloc import _CVNodeAlloc
from common.types import CompDict, BitNodes, ScopeDict, VerilogMetadata, YosysModule
from common.constants import COL_GAP, GATE_COL_GAP
from synthesis.hierarchical.scope import _cv_scope_id, _cv_layout
from synthesis.hierarchical.yosys_runner import run_yosys, yosys_script, check_module_exists
from synthesis.hierarchical.routing import (
    remap_comp_nodes, resolve_and_route, wire_nets, wired_node_ids,
)
from placement.layout import topo_sort_cells, place_cells, compute_col_x
from placement.ports import place_ports, compute_bbox
from synthesis.splitter_pass import insert_splitters


# ── Yosys param parsing / name cleaning ──────────────────────────────────

def _parse_yosys_param(val: str) -> int:
    """Convert a Yosys parameter value string to a decimal integer.

    Handles formats like:
      s32'00000000000000000000000000001000  -> 8   (signed binary)
      32'00000000000000000000000000001000   -> 8   (unsigned binary)
      plain binary digits                   -> int(val, 2)
    """
    raw: str = val
    signed: bool = raw.startswith("s")
    if signed:
        raw = raw[1:]
    if "'" in raw:
        width_str: str
        width_str, raw = raw.split("'", 1)
        width: int = int(width_str)
    else:
        width = len(raw)
    n: int = int(raw, 2)
    if signed and width and n >= (1 << (width - 1)):
        n -= 1 << width
    return n


def _clean_yosys_name(name: str, ymod: YosysModule | None = None) -> str:
    """Extract a readable name from a Yosys parameterized module name.

    Produces {component}-{param1_decimal}(-{param2_decimal}...) format.
    e.g. '$paramod\\mux\\N=s32'00...001000' -> 'mux-8'
         '$paramod\\rom\\DEPTH=...\\WIDTH=...' -> 'rom-256-8'
         '$paramod$abc123\\mux' with ymod params {S:2, N:8} -> 'mux-2-8'
    """
    if not name.startswith("$paramod"):
        return name

    parts: list[str] = name.split("\\")
    base: str | None = None
    params: list[str] = []
    for part in parts:
        if part.startswith("$paramod") or part.startswith("$"):
            continue
        if "=" in part:
            _, val = part.split("=", 1)
            try:
                params.append(str(_parse_yosys_param(val)))
            except (ValueError, IndexError):
                params.append(val)
        elif base is None:
            base = part
    if base is None:
        base = name.rsplit("\\", 1)[-1]

    if not params and ymod:
        for val in ymod.get("parameter_default_values", {}).values():
            if isinstance(val, str):
                try:
                    params.append(str(_parse_yosys_param(val)))
                except (ValueError, IndexError):
                    params.append(val)
            else:
                params.append(str(int(val)))

    if params:
        return f"{base}-{'-'.join(params)}"
    return base


# ── Single-module scope builder ──────────────────────────────────────────

def _build_yosys_scope(mod_name: str, ymod: YosysModule, na: _CVNodeAlloc, bit_nodes: BitNodes, sub_scope_ids: dict[str, dict[str, Any]],
                       gate_level: bool = False, check: bool = False) -> tuple[ScopeDict, str, dict[str, dict[str, Any]], list[str]]:
    """Build a CircuitVerse scope for a single Yosys module.

    Cells whose type matches another module in the netlist become SubCircuit
    references. All other cells go through the normal HL/gate dispatch.

    Returns (scope_dict, scope_id, port_info, subcircuit_types).
    port_info = {port_name: {"direction": dir, "width": bw, "x": pin_x, "y": pin_y}}
    """
    scope_id: str = _cv_scope_id()
    LAYOUT_W: int = 100
    min_gap: int = GATE_COL_GAP if gate_level else COL_GAP

    # ── Phase 0: insert splitters for width mismatches ────────────────────
    insert_splitters(ymod)

    # ── Phase A: place all cells (native + subcircuit) in one pass ────────

    _, col_cells, cell_depth = topo_sort_cells(ymod)
    col_x: dict[int, int] = compute_col_x(col_cells, min_col_gap=min_gap,
                           sub_scope_ids=sub_scope_ids)

    components, cell_positions, cv_subcircuits, sc_comps = place_cells(
        col_cells, na, bit_nodes, gate_level=gate_level, col_x=col_x,
        sub_scope_ids=sub_scope_ids)

    # Collect subcircuit types used in this module
    subcircuit_types: list[str] = []
    for cell_name, cell in ymod.get("cells", {}).items():
        if cell["type"] != "$scopeinfo" and cell["type"] in sub_scope_ids:
            if cell["type"] not in subcircuit_types:
                subcircuit_types.append(cell["type"])

    # ── Phase B: place ports outside the bounding box ──────────────────

    bbox = compute_bbox(col_cells, col_x, cell_positions, sc_comps,
                        sub_scope_ids=sub_scope_ids)
    cv_inputs, cv_outputs, cv_splitters, y_in, y_out = place_ports(
        ymod, na, bit_nodes, col_cells, col_x,
        cell_depth=cell_depth, cell_positions=cell_positions,
        bbox=bbox, layout_w=LAYOUT_W)

    # ── Wiring + routing ─────────────────────────────────────────────────

    sc_port_nids: set[int] = set()
    for sc in cv_subcircuits:
        sc_port_nids.update(sc["inputNodes"])

    wire_nets(na, bit_nodes)

    for sc in cv_subcircuits:
        sx, sy = sc["x"], sc["y"]
        for nid in sc["inputNodes"] + sc["outputNodes"]:
            na.set_parent_pos(nid, sx, sy)

    resolve_and_route(na, cv_inputs, cv_outputs, cv_splitters, components,
                      extra_comps=sc_comps, check=check)

    # Relocate SC port nodes to end of allNodes (CircuitVerse ordering)
    if sc_port_nids:
        old_nodes = na.nodes
        n: int = len(old_nodes)
        non_sc: list[int] = [i for i in range(n) if i not in sc_port_nids]
        sc_list: list[int] = [i for i in range(n) if i in sc_port_nids]
        new_order: list[int] = non_sc + sc_list
        remap: dict[int, int] = {old: new for new, old in enumerate(new_order)}
        na.nodes = [old_nodes[i] for i in new_order]
        na.abs_pos = [na.abs_pos[i] for i in new_order]
        for node in na.nodes:
            node.connections = [remap[c] for c in node.connections]
        remap_comp_nodes(cv_inputs + cv_outputs + cv_splitters, remap)
        for comp_list in components.values():
            remap_comp_nodes(comp_list, remap)
        for sc in cv_subcircuits:
            sc["inputNodes"] = [remap[x] for x in sc["inputNodes"]]
            sc["outputNodes"] = [remap[x] for x in sc["outputNodes"]]

    # Build port_info for parent scopes to use when placing this as SubCircuit
    port_info: dict[str, dict[str, Any]] = {}
    pin_y: int = 40
    for pname, pdata in ymod.get("ports", {}).items():
        bw: int = len(pdata["bits"])
        if pdata["direction"] == "input":
            port_info[pname] = {"direction": "input", "width": bw, "x": 0, "y": pin_y}
            pin_y += 20
    pin_y = 40
    for pname, pdata in ymod.get("ports", {}).items():
        bw = len(pdata["bits"])
        if pdata["direction"] == "output":
            port_info[pname] = {"direction": "output", "width": bw, "x": LAYOUT_W, "y": pin_y}
            pin_y += 20

    # Merge splitters from port placement and $cv_splitter cells
    all_splitters: list[CompDict] = cv_splitters + components.pop("Splitter", [])
    _log.debug("scope %s: %d splitter(s) (port=%d, cell=%d)",
               mod_name, len(all_splitters), len(cv_splitters),
               len(all_splitters) - len(cv_splitters))

    # Build component dict (CompDict objects + SubCircuit plain dicts)
    scope_components: dict[str, list[Any]] = {}
    scope_components["Input"] = list(cv_inputs)
    scope_components["Output"] = list(cv_outputs)
    if all_splitters:
        scope_components["Splitter"] = list(all_splitters)
    if cv_subcircuits:
        scope_components["SubCircuit"] = cv_subcircuits
    for k, v in components.items():
        scope_components[k] = list(v)

    scope: ScopeDict = ScopeDict(
        layout=_cv_layout(len(cv_inputs), len(cv_outputs)),
        verilogMetadata=VerilogMetadata(),
        allNodes=na.nodes,
        id=int(scope_id),
        name=_clean_yosys_name(mod_name, ymod),
        nodes=wired_node_ids(na),
        components=scope_components,
    )

    return scope, scope_id, port_info, subcircuit_types


# ── Public API ───────────────────────────────────────────────────────────

def generate_circuitverse_yosys(verilog_paths: list[str], top_name: str, gate_level: bool = False,
                                flatten: bool = True, cache_dir: str | None = None,
                                check: bool = False) -> tuple[ScopeDict, dict[str, Any]]:
    """Generate CircuitVerse JSON via Yosys synthesis.

    When *flatten* is True (default), Yosys flattens all modules into one scope.
    When *flatten* is False, each module becomes its own CircuitVerse scope with
    sub-module instantiations as SubCircuit components.

    When *gate_level* is True, decomposes to 1-bit primitives.
    When *cache_dir* is provided, routed scopes are cached to disk (hier mode).
    """
    _cv_scope_id.reset()
    netlist: dict[str, Any] = run_yosys(yosys_script(verilog_paths, top_name, gate_level, flatten=flatten))
    check_module_exists(netlist, top_name)

    modules: dict[str, YosysModule] = netlist["modules"]

    # Build dependency order: leaf modules first
    mod_deps: dict[str, set[str]] = {}
    for mname, mdata in modules.items():
        deps: set[str] = set()
        for _, cell in mdata.get("cells", {}).items():
            if cell["type"] in modules:
                deps.add(cell["type"])
        mod_deps[mname] = deps

    # Topological sort
    ordered: list[str] = []
    visited: set[str] = set()

    def _visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        for dep in mod_deps.get(name, set()):
            _visit(dep)
        ordered.append(name)

    _visit(top_name)

    # Optional scope cache (keyed by MD5 of all source files)
    cache: ScopeCache | None = None
    if cache_dir:
        from synthesis.hierarchical.scope_cache import ScopeCache
        cache = ScopeCache(cache_dir, verilog_paths)

    # Build scopes bottom-up
    sub_scope_ids: dict[str, dict[str, Any]] = {}
    scopes: list[ScopeDict] = []

    for mod_name in ordered:
        ymod: YosysModule = modules[mod_name]

        # Try cache lookup
        cached: dict[str, Any] | None = cache.get(mod_name) if cache else None

        if cached is not None:
            scope: ScopeDict = cached["scope"]
            port_info: dict[str, dict[str, Any]] = cached["port_info"]
            scope_id: str = _cv_scope_id()
            scope.id = int(scope_id)
            for i, sc in enumerate(scope.components.get("SubCircuit", [])):
                child_type: str = cached["subcircuit_types"][i]
                sc["id"] = sub_scope_ids[child_type]["scope_id"]
        else:
            na: _CVNodeAlloc = _CVNodeAlloc()
            bit_nodes: BitNodes = {}
            scope, scope_id, port_info, sc_types = _build_yosys_scope(
                mod_name, ymod, na, bit_nodes, sub_scope_ids,
                gate_level=gate_level, check=check)
            if cache:
                cache.put(mod_name, scope, port_info, sc_types)

        sub_scope_ids[mod_name] = {
            "scope_id": scope_id,
            "port_info": port_info,
            "layout_w": 100,
        }

        if mod_name != top_name:
            scopes.append(scope)

    # The top module scope is the main circuit
    top_scope: ScopeDict = scope  # last one built
    top_scope.verilogMetadata.isMainCircuit = True
    top_scope.verilogMetadata.subCircuitScopeIds = [
        s["scope_id"] for mname, s in sub_scope_ids.items()
        if mname != top_name
    ]
    top_scope.scopes = scopes
    top_scope.logixClipBoardData = True

    return top_scope, netlist
