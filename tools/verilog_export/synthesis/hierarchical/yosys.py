"""CircuitVerse generation via Yosys synthesis.

Supports three modes:
  gate_level=True   — decompose to 1-bit primitives (AND/OR/NOT/DFF/MUX)
  gate_level=False  — preserve high-level Yosys cells, flattened (adders, comparators, etc.)
  hierarchical      — preserve high-level cells AND module hierarchy (SubCircuit scopes)
"""

import json
import os
import subprocess
import tempfile

from common.node_alloc import _CVNodeAlloc
from synthesis.hierarchical.scope import _cv_scope_id, _cv_layout
from common.constants import CELL_GAP, COL_GAP, GATE_COL_GAP
from placement.layout import topo_sort_cells, place_cells, compute_col_x
from placement.ports import place_ports


def _run_yosys(script):
    """Run a Yosys script, return parsed JSON output.

    Raises RuntimeError if Yosys exits with a non-zero status.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        cmd = ["yosys", "-p", script.format(out=tmp_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Yosys failed:\n{result.stderr}")
        with open(tmp_path) as f:
            return json.load(f)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _yosys_script(verilog_paths, top_name, gate_level=False, flatten=True):
    """Build a Yosys synthesis script string."""
    read_cmds = "; ".join(f"read_verilog {p}" for p in verilog_paths)
    if gate_level:
        synth_steps = (
            "techmap; opt; "
            "abc -g AND,NAND,OR,NOR,XOR,XNOR,MUX; opt; "
        )
    else:
        synth_steps = "memory -nomap; pmuxtree; opt; "
    flatten_cmd = "flatten; opt; " if flatten else ""
    return (
        f"{read_cmds}; "
        f"hierarchy -top {top_name}; "
        f"proc; opt; {flatten_cmd}"
        f"{synth_steps}"
        f"clean -purge; "
        f"write_json {{out}}"
    )


def _yosys_synth(verilog_paths, top_name, gate_level=False):
    """Run Yosys synthesis (flattened) and return the JSON netlist dict."""
    return _run_yosys(_yosys_script(verilog_paths, top_name, gate_level, flatten=True))


def _remap_comp_nodes(comps, remap):
    """Remap node IDs in component customData.nodes dicts."""
    for comp in comps:
        cd = comp["customData"]
        for k, v in cd["nodes"].items():
            if isinstance(v, int):
                cd["nodes"][k] = remap[v]
            elif isinstance(v, list):
                cd["nodes"][k] = [remap[x] for x in v]


def _set_node_abs_positions(na, all_comps):
    """Scan placed components and set absolute positions for their nodes."""
    for comp in all_comps:
        cx, cy = comp["x"], comp["y"]
        direction = comp.get("direction", "RIGHT")
        cd = comp.get("customData", {})
        nodes = cd.get("nodes", {})
        for val in nodes.values():
            if isinstance(val, int):
                na.set_parent_pos(val, cx, cy, direction)
            elif isinstance(val, list):
                for nid in val:
                    if isinstance(nid, int):
                        na.set_parent_pos(nid, cx, cy, direction)


def _resolve_and_route(na, cv_inputs, cv_outputs, cv_splitters, components,
                       extra_comps=None, check=False):
    """Collect all components, set absolute positions, run orthogonal routing.

    Returns the full component list used for routing.
    """
    all_comps = cv_inputs + cv_outputs + cv_splitters
    for comp_list in components.values():
        all_comps.extend(comp_list)
    if extra_comps:
        all_comps.extend(extra_comps)
    _set_node_abs_positions(na, all_comps)
    na.route_orthogonal(all_comps)
    if check:
        na.verify_routing(all_comps)
    return all_comps


def generate_circuitverse_yosys(verilog_paths, top_name, gate_level=False, check=False):
    """Generate CircuitVerse JSON via Yosys synthesis.

    When gate_level=True, decomposes to 1-bit primitives.
    When gate_level=False, preserves high-level cells (adders, comparators, etc.).
    """
    _cv_scope_id.reset()
    netlist = _yosys_synth(verilog_paths, top_name, gate_level=gate_level)

    if top_name not in netlist.get("modules", {}):
        avail = list(netlist.get("modules", {}).keys())
        raise RuntimeError(
            f"Module '{top_name}' not in Yosys output. Available: {avail}")

    ymod = netlist["modules"][top_name]
    na = _CVNodeAlloc()
    bit_nodes = {}

    _, col_cells, cell_depth = topo_sort_cells(ymod)
    min_gap = GATE_COL_GAP if gate_level else COL_GAP
    col_x = compute_col_x(col_cells, min_col_gap=min_gap)
    components, cell_positions, _, _ = place_cells(
        col_cells, na, bit_nodes, gate_level=gate_level, col_x=col_x)
    from placement.ports import compute_bbox
    bbox = compute_bbox(col_cells, col_x, cell_positions, [])
    cv_inputs, cv_outputs, cv_splitters, y_in, y_out = place_ports(
        ymod, na, bit_nodes, col_cells, col_x,
        cell_depth=cell_depth, cell_positions=cell_positions, bbox=bbox)

    # Wire nodes sharing the same Yosys net — chain topology
    # (each node connects to the next, not full mesh)
    for _, node_ids in bit_nodes.items():
        for i in range(len(node_ids) - 1):
            na.connect(node_ids[i], node_ids[i + 1])

    _resolve_and_route(na, cv_inputs, cv_outputs, cv_splitters, components,
                       check=check)

    wired_ids = sorted(
        i for i, n in enumerate(na.nodes)
        if n["type"] == 2 and n["connections"]
    )

    rightmost_col = max(col_x.values()) if col_x else 0
    rightmost_port = max((c["x"] for c in cv_outputs), default=0)
    total_w = max(rightmost_col + 400, rightmost_port + 200) if (rightmost_col or rightmost_port) else 600

    return {
        "layout": {
            "width": total_w,
            "height": max(y_in, y_out, max(
                sum(1 for _ in cc) * CELL_GAP
                for cc in col_cells.values()
            ) if col_cells else 0) + 40,
            "title_x": 50,
            "title_y": 13,
            "titleEnabled": True,
        },
        "verilogMetadata": {
            "isVerilogCircuit": False,
            "isMainCircuit": True,
            "code": "",
            "subCircuitScopeIds": [],
        },
        "allNodes": na.nodes,
        "id": int(_cv_scope_id()),
        "name": top_name,
        "Input": cv_inputs,
        "Output": cv_outputs,
        **({"Splitter": cv_splitters} if cv_splitters else {}),
        **{k: v for k, v in components.items()},
        "restrictedCircuitElementsUsed": [],
        "nodes": wired_ids,
        "scopes": [],
        "logixClipBoardData": True,
    }, netlist


# ── Hierarchical (non-flattened) mode ─────────────────────────────────────

def _yosys_elaborate(verilog_paths, top_name, gate_level=False):
    """Run Yosys elaboration without flatten — preserves module hierarchy."""
    return _run_yosys(_yosys_script(verilog_paths, top_name, gate_level, flatten=False))


def _clean_yosys_name(name):
    """Extract a readable name from a Yosys parameterized module name.

    e.g. '$paramod$abc123\\mux' -> 'mux' (with hash for uniqueness)
    """
    if name.startswith("$paramod"):
        # Extract the base module name after the last backslash
        base = name.rsplit("\\", 1)[-1] if "\\" in name else name
        # Extract hash prefix for uniqueness
        parts = name.split("$")
        h = parts[2][:6] if len(parts) > 2 else ""
        return f"{base}_{h}" if h else base
    return name


def _build_yosys_scope(mod_name, ymod, na, bit_nodes, sub_scope_ids,
                       gate_level=False):
    """Build a CircuitVerse scope for a single Yosys module.

    Cells whose type matches another module in the netlist become SubCircuit
    references. All other cells go through the normal HL/gate dispatch.

    Returns (scope_dict, scope_id, port_info, subcircuit_types).
    port_info = {port_name: {"direction": dir, "width": bw, "x": pin_x, "y": pin_y}}
    """
    scope_id = _cv_scope_id()
    LAYOUT_W = 100
    min_gap = GATE_COL_GAP if gate_level else COL_GAP

    # ── Phase A: place all cells (native + subcircuit) in one pass ────────

    # Unified topo-sort over all non-scopeinfo cells
    _, col_cells, cell_depth = topo_sort_cells(ymod)
    col_x = compute_col_x(col_cells, min_col_gap=min_gap,
                           sub_scope_ids=sub_scope_ids)

    # Unified placement — native cells dispatch to handlers, subcircuit
    # cells dispatch to _place_subcircuit, all in the same column loop.
    components, cell_positions, cv_subcircuits, sc_comps = place_cells(
        col_cells, na, bit_nodes, gate_level=gate_level, col_x=col_x,
        sub_scope_ids=sub_scope_ids)

    # Collect subcircuit types used in this module
    subcircuit_types = []
    for cell_name, cell in ymod.get("cells", {}).items():
        if cell["type"] != "$scopeinfo" and cell["type"] in sub_scope_ids:
            if cell["type"] not in subcircuit_types:
                subcircuit_types.append(cell["type"])

    # ── Phase B: place ports outside the bounding box ──────────────────

    from placement.ports import compute_bbox
    bbox = compute_bbox(col_cells, col_x, cell_positions, sc_comps,
                        sub_scope_ids=sub_scope_ids)
    cv_inputs, cv_outputs, cv_splitters, y_in, y_out = place_ports(
        ymod, na, bit_nodes, col_cells, col_x,
        cell_depth=cell_depth, cell_positions=cell_positions,
        bbox=bbox, layout_w=LAYOUT_W)

    # ── Wiring + routing ─────────────────────────────────────────────────

    # Collect SC input port node IDs (to relocate after routing)
    sc_port_nids = set()
    for sc in cv_subcircuits:
        sc_port_nids.update(sc["inputNodes"])

    # Wire all nodes sharing the same Yosys net — chain topology
    for _, node_ids in bit_nodes.items():
        for i in range(len(node_ids) - 1):
            na.connect(node_ids[i], node_ids[i + 1])

    # Set positions for subcircuit nodes before routing
    for sc in cv_subcircuits:
        sx, sy = sc["x"], sc["y"]
        for nid in sc["inputNodes"] + sc["outputNodes"]:
            na.set_parent_pos(nid, sx, sy)

    # Route with subcircuit body-blocking pseudo-components included
    _resolve_and_route(na, cv_inputs, cv_outputs, cv_splitters, components,
                       extra_comps=sc_comps)

    # Relocate SC port nodes to end of allNodes (CircuitVerse ordering)
    if sc_port_nids:
        old_nodes = na.nodes
        n = len(old_nodes)
        non_sc = [i for i in range(n) if i not in sc_port_nids]
        sc_list = [i for i in range(n) if i in sc_port_nids]
        new_order = non_sc + sc_list
        remap = {old: new for new, old in enumerate(new_order)}
        na.nodes = [old_nodes[i] for i in new_order]
        na.abs_pos = [na.abs_pos[i] for i in new_order]
        for node in na.nodes:
            node["connections"] = [remap[c] for c in node["connections"]]
        _remap_comp_nodes(cv_inputs + cv_outputs + cv_splitters, remap)
        for comp_list in components.values():
            _remap_comp_nodes(comp_list, remap)
        for sc in cv_subcircuits:
            sc["inputNodes"] = [remap[x] for x in sc["inputNodes"]]
            sc["outputNodes"] = [remap[x] for x in sc["outputNodes"]]

    wired_ids = sorted(
        i for i, n in enumerate(na.nodes)
        if n["type"] == 2 and n["connections"]
    )

    # ── Layout dimensions ────────────────────────────────────────────────

    # Account for both cell columns and output port positions
    rightmost_x = max(col_x.values()) if col_x else 0
    rightmost_port = max((c["x"] for c in cv_outputs), default=0)
    total_w = max(rightmost_x + 400, rightmost_port + 200) if (rightmost_x or rightmost_port) else 600

    # Build port_info for parent scopes to use when placing this as SubCircuit
    port_info = {}
    pin_y = 40
    for pname, pdata in ymod.get("ports", {}).items():
        bw = len(pdata["bits"])
        if pdata["direction"] == "input":
            port_info[pname] = {"direction": "input", "width": bw, "x": 0, "y": pin_y}
            pin_y += 20
    pin_y = 40
    for pname, pdata in ymod.get("ports", {}).items():
        bw = len(pdata["bits"])
        if pdata["direction"] == "output":
            port_info[pname] = {"direction": "output", "width": bw, "x": LAYOUT_W, "y": pin_y}
            pin_y += 20

    scope = {
        "layout": _cv_layout(len(cv_inputs), len(cv_outputs)),
        "verilogMetadata": {
            "isVerilogCircuit": False,
            "isMainCircuit": False,
            "code": "",
            "subCircuitScopeIds": [],
        },
        "allNodes": na.nodes,
        "id": int(scope_id),
        "name": _clean_yosys_name(mod_name),
        "Input": cv_inputs,
        "Output": cv_outputs,
        **({"Splitter": cv_splitters} if cv_splitters else {}),
        **({"SubCircuit": cv_subcircuits} if cv_subcircuits else {}),
        **{k: v for k, v in components.items()},
        "restrictedCircuitElementsUsed": [],
        "nodes": wired_ids,
    }

    return scope, scope_id, port_info, subcircuit_types


def generate_circuitverse_yosys_hier(verilog_paths, top_name, cache_dir=None,
                                     gate_level=False):
    """Generate CircuitVerse JSON via Yosys — hierarchical (non-flattened).

    Each Yosys-elaborated module becomes its own CircuitVerse scope.
    Sub-module instantiations appear as SubCircuit components.

    When *cache_dir* is provided, routed scopes are cached to disk so that
    repeated exports skip placement + routing for unchanged modules.
    When *gate_level* is True, each module is decomposed to 1-bit primitives.
    """
    _cv_scope_id.reset()
    netlist = _yosys_elaborate(verilog_paths, top_name, gate_level=gate_level)

    if top_name not in netlist.get("modules", {}):
        avail = list(netlist.get("modules", {}).keys())
        raise RuntimeError(
            f"Module '{top_name}' not in Yosys output. Available: {avail}")

    modules = netlist["modules"]

    # Build dependency order: leaf modules first
    # A module depends on another if it has cells whose type is that module
    mod_deps = {}
    for mname, mdata in modules.items():
        deps = set()
        for _, cell in mdata.get("cells", {}).items():
            if cell["type"] in modules:
                deps.add(cell["type"])
        mod_deps[mname] = deps

    # Topological sort
    ordered = []
    visited = set()

    def _visit(name):
        if name in visited:
            return
        visited.add(name)
        for dep in mod_deps.get(name, set()):
            _visit(dep)
        ordered.append(name)

    _visit(top_name)

    # Optional scope cache (keyed by MD5 of all source files)
    cache = None
    if cache_dir:
        from synthesis.hierarchical.scope_cache import ScopeCache
        cache = ScopeCache(cache_dir, verilog_paths)

    # Build scopes bottom-up
    # sub_scope_ids maps yosys_module_name -> {"scope_id": str, "port_info": dict}
    sub_scope_ids = {}
    scopes = []

    for mod_name in ordered:
        ymod = modules[mod_name]

        # Try cache lookup
        cached = cache.get(mod_name) if cache else None

        if cached is not None:
            scope = cached["scope"]
            port_info = cached["port_info"]
            # Assign fresh scope ID
            scope_id = _cv_scope_id()
            scope["id"] = int(scope_id)
            # Remap SubCircuit child IDs to current run's scope IDs
            for i, sc in enumerate(scope.get("SubCircuit", [])):
                child_type = cached["subcircuit_types"][i]
                sc["id"] = sub_scope_ids[child_type]["scope_id"]
        else:
            na = _CVNodeAlloc()
            bit_nodes = {}
            scope, scope_id, port_info, sc_types = _build_yosys_scope(
                mod_name, ymod, na, bit_nodes, sub_scope_ids,
                gate_level=gate_level)
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
    top_scope = scope  # last one built
    top_scope["verilogMetadata"]["isMainCircuit"] = True
    top_scope["verilogMetadata"]["subCircuitScopeIds"] = [
        s["scope_id"] for mname, s in sub_scope_ids.items()
        if mname != top_name
    ]
    top_scope["scopes"] = scopes
    top_scope["logixClipBoardData"] = True

    return top_scope, netlist
