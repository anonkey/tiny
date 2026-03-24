"""CircuitVerse generation via Yosys synthesis.

Supports three modes:
  gate_level=True   — decompose to 1-bit primitives (AND/OR/NOT/DFF/MUX)
  gate_level=False  — preserve high-level Yosys cells, flattened (adders, comparators, etc.)
  hierarchical      — preserve high-level cells AND module hierarchy (SubCircuit scopes)
"""

import json
import os
import subprocess
import sys
import tempfile

from cv_common import _CVNodeAlloc, _cv_scope_id, _cv_layout
from circuitverse.yosys_layout import CELL_GAP, COL_GAP, topo_sort_cells, place_cells, compute_col_x
from circuitverse.yosys_ports import place_ports
from circuitverse.components._common import X_START


def _yosys_synth(verilog_paths, top_name, gate_level=False):
    """Run Yosys synthesis and return the JSON netlist dict."""
    read_cmds = "; ".join(f"read_verilog {p}" for p in verilog_paths)
    if gate_level:
        synth_steps = (
            "techmap; opt; "
            "abc -g AND,NAND,OR,NOR,XOR,XNOR,MUX; opt; "
        )
    else:
        synth_steps = "memory -nomap; pmuxtree; opt; "
    script = (
        f"{read_cmds}; "
        f"hierarchy -top {top_name}; "
        f"proc; opt; flatten; opt; "
        f"{synth_steps}"
        f"clean -purge; "
        f"write_json {{out}}"
    )
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        cmd = ["yosys", "-p", script.format(out=tmp_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Yosys error:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        with open(tmp_path) as f:
            return json.load(f)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


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


def generate_circuitverse_yosys(verilog_paths, top_name, gate_level=False):
    """Generate CircuitVerse JSON via Yosys synthesis.

    When gate_level=True, decomposes to 1-bit primitives.
    When gate_level=False, preserves high-level cells (adders, comparators, etc.).
    """
    _cv_scope_id._counter = -1
    netlist = _yosys_synth(verilog_paths, top_name, gate_level=gate_level)

    if top_name not in netlist.get("modules", {}):
        avail = list(netlist.get("modules", {}).keys())
        print(f"Module '{top_name}' not in Yosys output. Available: {avail}",
              file=sys.stderr)
        sys.exit(1)

    ymod = netlist["modules"][top_name]
    na = _CVNodeAlloc()
    bit_nodes = {}

    _, col_cells = topo_sort_cells(ymod)
    col_x = compute_col_x(col_cells)
    cv_inputs, cv_outputs, cv_splitters, y_in, y_out = place_ports(
        ymod, na, bit_nodes, col_cells, col_x)
    components = place_cells(col_cells, na, bit_nodes, gate_level=gate_level, col_x=col_x)

    # Wire nodes sharing the same Yosys net — chain topology
    # (each node connects to the next, not full mesh)
    for _, node_ids in bit_nodes.items():
        for i in range(len(node_ids) - 1):
            na.connect(node_ids[i], node_ids[i + 1])

    # Compute absolute node positions from component placements, then
    # insert routing nodes so all wires are horizontal or vertical.
    all_comps = cv_inputs + cv_outputs + cv_splitters
    for comp_list in components.values():
        all_comps.extend(comp_list)
    _set_node_abs_positions(na, all_comps)
    na.route_orthogonal(all_comps)
    na.verify_routing(all_comps)

    wired_ids = sorted(set(
        i for i, n in enumerate(na.nodes) if n["connections"]
    ))

    max_depth = max(col_cells.keys()) if col_cells else 0
    total_w = (max_depth + 2) * COL_GAP + 200

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
    }


# ── Hierarchical (non-flattened) mode ─────────────────────────────────────

def _yosys_elaborate(verilog_paths, top_name):
    """Run Yosys elaboration without flatten — preserves module hierarchy."""
    read_cmds = "; ".join(f"read_verilog {p}" for p in verilog_paths)
    script = (
        f"{read_cmds}; "
        f"hierarchy -top {top_name}; "
        f"proc; opt; "
        f"memory -nomap; pmuxtree; opt; "
        f"clean -purge; "
        f"write_json {{out}}"
    )
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        cmd = ["yosys", "-p", script.format(out=tmp_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Yosys error:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        with open(tmp_path) as f:
            return json.load(f)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


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


def _build_yosys_scope(mod_name, ymod, na, bit_nodes, sub_scope_ids):
    """Build a CircuitVerse scope for a single Yosys module.

    Cells whose type matches another module in the netlist become SubCircuit
    references. All other cells go through the normal HL dispatch.

    Returns (scope_dict, scope_id, port_info).
    port_info = {port_name: {"direction": dir, "width": bw, "x": pin_x, "y": pin_y}}
    """
    scope_id = _cv_scope_id()

    # Separate cells into native (HL dispatch) and subcircuit references
    native_cells = []
    subcircuit_cells = []
    for cell_name, cell in ymod.get("cells", {}).items():
        if cell["type"] == "$scopeinfo":
            continue
        if cell["type"] in sub_scope_ids:
            subcircuit_cells.append((cell_name, cell))
        else:
            native_cells.append((cell_name, cell))

    # Topo-sort native cells using existing infrastructure
    # Build a fake ymod with only native cells for topo_sort
    native_ymod = {
        "ports": ymod.get("ports", {}),
        "cells": {n: c for n, c in native_cells},
    }
    _, col_cells = topo_sort_cells(native_ymod)

    # Place ports and native cells
    col_x = compute_col_x(col_cells)
    cv_inputs, cv_outputs, cv_splitters, y_in, y_out = place_ports(
        ymod, na, bit_nodes, col_cells, col_x)
    components = place_cells(col_cells, na, bit_nodes, gate_level=False, col_x=col_x)

    # Place subcircuit instances
    cv_subcircuits = []
    max_native_depth = max(col_cells.keys()) if col_cells else 0

    # Topo-sort subcircuit cells
    bit_producer = {}
    for cn, cc in native_cells:
        dirs = cc.get("port_directions", {})
        for pn, d in dirs.items():
            if d == "output":
                for b in cc["connections"].get(pn, []):
                    if not isinstance(b, str):
                        bit_producer[b] = cn
    for cn, cc in subcircuit_cells:
        dirs = cc.get("port_directions", {})
        for pn, d in dirs.items():
            if d == "output":
                for b in cc["connections"].get(pn, []):
                    if not isinstance(b, str):
                        bit_producer[b] = cn

    sc_by_name = {n: c for n, c in subcircuit_cells}
    sc_depth = {}

    def _sc_depth(cname, visiting=None):
        if cname in sc_depth:
            return sc_depth[cname]
        if visiting is None:
            visiting = set()
        if cname in visiting:
            return 0
        visiting.add(cname)
        cell = sc_by_name.get(cname)
        if not cell:
            return 0
        dirs = cell.get("port_directions", {})
        max_d = 0
        for pn, d in dirs.items():
            if d != "input":
                continue
            for b in cell["connections"].get(pn, []):
                if not isinstance(b, str) and b in bit_producer:
                    prod = bit_producer[b]
                    if prod != cname and prod in sc_by_name:
                        max_d = max(max_d, _sc_depth(prod, visiting) + 1)
        sc_depth[cname] = max_d
        return max_d

    for cn, _ in subcircuit_cells:
        _sc_depth(cn)

    sorted_sc = sorted(subcircuit_cells,
                       key=lambda nc: (sc_depth.get(nc[0], 0),
                                       subcircuit_cells.index(nc)))

    # Group into columns
    sc_columns = {}
    for cn, cc in sorted_sc:
        d = sc_depth.get(cn, 0)
        sc_columns.setdefault(d, []).append((cn, cc))

    LAYOUT_W = 120
    SC_COL_GAP = 200
    SC_ROW_GAP = 20
    sc_x_start = X_START + (max_native_depth + 1) * COL_GAP if col_cells else X_START

    for depth in sorted(sc_columns.keys()):
        col_x = sc_x_start + depth * (LAYOUT_W + SC_COL_GAP)
        col_y = 0
        for cn, cc in sc_columns[depth]:
            sid = sub_scope_ids[cc["type"]]
            port_info = sid["port_info"]
            dirs = cc.get("port_directions", {})
            conns = cc["connections"]

            input_nodes = []
            output_nodes = []

            for pname, d in dirs.items():
                bits = conns.get(pname, [])
                bw = len(bits)
                pi = port_info.get(pname, {"x": 0, "y": 20})
                if d == "input":
                    nid = na.alloc(pi["x"], pi["y"], 0, bw)
                    input_nodes.append(nid)
                    for b in bits:
                        if not isinstance(b, str):
                            bit_nodes.setdefault(b, []).append(nid)
                else:
                    nid = na.alloc(pi["x"], pi["y"], 1, bw)
                    output_nodes.append(nid)
                    for b in bits:
                        if not isinstance(b, str):
                            bit_nodes.setdefault(b, []).append(nid)

            n_max = max(len(input_nodes), len(output_nodes), 1)
            h = 20 * n_max + 20

            cv_subcircuits.append({
                "x": col_x, "y": col_y,
                "id": sid["scope_id"],
                "label": cn,
                "labelDirection": "RIGHT",
                "inputNodes": input_nodes,
                "outputNodes": output_nodes,
                "version": "2.0",
            })
            col_y += h + SC_ROW_GAP

    # Wire all nodes sharing the same Yosys net
    for _, node_ids in bit_nodes.items():
        for i in range(len(node_ids) - 1):
            na.connect(node_ids[i], node_ids[i + 1])

    # Compute absolute positions and route
    all_comps = cv_inputs + cv_outputs + cv_splitters
    for comp_list in components.values():
        all_comps.extend(comp_list)
    _set_node_abs_positions(na, all_comps)
    # Set positions for subcircuit nodes too
    for sc in cv_subcircuits:
        sx, sy = sc["x"], sc["y"]
        for nid in sc["inputNodes"] + sc["outputNodes"]:
            na.set_parent_pos(nid, sx, sy)
    na.route_orthogonal(all_comps)

    wired_ids = sorted(set(
        i for i, n in enumerate(na.nodes) if n["connections"]
    ))

    max_sc_depth = max(sc_columns.keys()) if sc_columns else 0
    total_cols = (max_native_depth + 1) + (max_sc_depth + 1) if sc_columns else (max_native_depth + 1)
    total_w = total_cols * COL_GAP + 400

    # Build port_info for parent scopes to use when placing this as a SubCircuit
    port_info = {}
    pin_y = 20
    for pname, pdata in ymod.get("ports", {}).items():
        bw = len(pdata["bits"])
        if pdata["direction"] == "input":
            port_info[pname] = {"direction": "input", "width": bw, "x": 0, "y": pin_y}
            pin_y += 20
    pin_y = 20
    for pname, pdata in ymod.get("ports", {}).items():
        bw = len(pdata["bits"])
        if pdata["direction"] == "output":
            port_info[pname] = {"direction": "output", "width": bw, "x": LAYOUT_W, "y": pin_y}
            pin_y += 20

    sub_scope_id_list = [s["scope_id"] for s in sub_scope_ids.values()
                         if any(c["type"] == t for t in sub_scope_ids
                                for _, c in subcircuit_cells)]

    scope = {
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

    return scope, scope_id, port_info


def generate_circuitverse_yosys_hier(verilog_paths, top_name):
    """Generate CircuitVerse JSON via Yosys — hierarchical (non-flattened).

    Each Yosys-elaborated module becomes its own CircuitVerse scope.
    Sub-module instantiations appear as SubCircuit components.
    """
    _cv_scope_id._counter = -1
    netlist = _yosys_elaborate(verilog_paths, top_name)

    if top_name not in netlist.get("modules", {}):
        avail = list(netlist.get("modules", {}).keys())
        print(f"Module '{top_name}' not in Yosys output. Available: {avail}",
              file=sys.stderr)
        sys.exit(1)

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

    # Build scopes bottom-up
    # sub_scope_ids maps yosys_module_name -> {"scope_id": str, "port_info": dict}
    sub_scope_ids = {}
    scopes = []

    for mod_name in ordered:
        ymod = modules[mod_name]
        na = _CVNodeAlloc()
        bit_nodes = {}

        scope, scope_id, port_info = _build_yosys_scope(
            mod_name, ymod, na, bit_nodes, sub_scope_ids)

        sub_scope_ids[mod_name] = {
            "scope_id": scope_id,
            "port_info": port_info,
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

    return top_scope
