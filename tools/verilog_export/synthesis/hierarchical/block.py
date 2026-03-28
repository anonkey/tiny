"""CircuitVerse JSON generation (block-level)."""
from __future__ import annotations

import re
from typing import Any

from common.node_alloc import _CVNodeAlloc
from common.types import CompDict, CVCustomData, ScopeDict
from synthesis.hierarchical.scope import _cv_scope_id, _cv_layout, _build_cv_scope
from common.emit import unique_pos, CTOR_PARAMS_KEY

import verilog_parser


def generate_circuitverse(top_mod: verilog_parser.Module,
                          sub_modules: list[verilog_parser.Module]) -> dict[str, Any]:
    """Generate a CircuitVerse-compatible JSON dict.

    Top-level ports become Input/Output components. Each unique submodule
    type gets a scope definition. Instances become SubCircuit components
    wired together via allNodes connections.
    """
    _cv_scope_id.reset()
    na: _CVNodeAlloc = _CVNodeAlloc()
    mod_map: dict[str, verilog_parser.Module] = {m.name: m for m in sub_modules}

    # --- Build subcircuit scopes ---
    scope_ids: dict[str, str] = {}    # module_name -> scope_id
    scope_pins: dict[str, dict[str, dict[str, Any]]] = {}   # module_name -> {port_name: {x, y}}
    scopes: list[ScopeDict] = []
    seen: set[str] = set()
    for inst in top_mod.instances:
        if inst.module_name in seen or inst.module_name not in mod_map:
            continue
        seen.add(inst.module_name)
        sub: verilog_parser.Module = mod_map[inst.module_name]
        scope: ScopeDict
        sid: str
        pins: dict[str, dict[str, Any]]
        scope, sid, pins = _build_cv_scope(sub, na)
        scope_ids[inst.module_name] = sid
        scope_pins[inst.module_name] = pins
        scopes.append(scope)

    # --- Net map: net_name -> list of node IDs (to connect later) ---
    net_nodes: dict[str, list[int]] = {}

    def _register_net(net_name: str, node_id: int) -> None:
        net: str = re.sub(r'\[.*?\]', '', net_name).strip()
        if not net:
            return
        net_nodes.setdefault(net, []).append(node_id)

    # --- Topological sort of instances for left-to-right data flow ---
    inst_list: list[verilog_parser.Instance] = []
    for inst in top_mod.instances:
        sub: verilog_parser.Module | None = mod_map.get(inst.module_name)
        if sub and inst.module_name in scope_ids:
            inst_list.append(inst)

    net_producer: dict[str, str] = {}   # net_name -> inst_name
    net_consumers: dict[str, list[str]] = {}  # net_name -> [inst_name, ...]

    for inst in inst_list:
        sub_m: verilog_parser.Module = mod_map[inst.module_name]
        port_dir: dict[str, str] = {p.name: p.direction for p in sub_m.ports}
        for port_name, net_expr in inst.connections.items():
            net: str = re.sub(r'\[.*?\]', '', net_expr).strip()
            if not net:
                continue
            d: str = port_dir.get(port_name, "input")
            if d == "output":
                net_producer[net] = inst.inst_name
            else:
                net_consumers.setdefault(net, []).append(inst.inst_name)

    # Compute depth
    inst_depth: dict[str, int] = {}
    inst_by_name: dict[str, verilog_parser.Instance] = {inst.inst_name: inst for inst in inst_list}

    def _get_depth(iname: str, visiting: set[str] | None = None) -> int:
        if iname in inst_depth:
            return inst_depth[iname]
        if visiting is None:
            visiting = set()
        if iname in visiting:
            return 0
        visiting.add(iname)
        inst_i: verilog_parser.Instance = inst_by_name[iname]
        sub_d: verilog_parser.Module = mod_map[inst_i.module_name]
        port_dir_d: dict[str, str] = {p.name: p.direction for p in sub_d.ports}
        max_dep: int = 0
        for port_name, net_expr in inst_i.connections.items():
            net: str = re.sub(r'\[.*?\]', '', net_expr).strip()
            d: str = port_dir_d.get(port_name, "input")
            if d == "input" and net in net_producer:
                producer: str = net_producer[net]
                if producer != iname:
                    max_dep = max(max_dep, _get_depth(producer, visiting) + 1)
        inst_depth[iname] = max_dep
        return max_dep

    for inst in inst_list:
        _get_depth(inst.inst_name)

    sorted_insts: list[verilog_parser.Instance] = sorted(
        inst_list, key=lambda i: (inst_depth[i.inst_name], inst_list.index(i)))

    columns: dict[int, list[verilog_parser.Instance]] = {}
    for inst in sorted_insts:
        d: int = inst_depth[inst.inst_name]
        columns.setdefault(d, []).append(inst)

    # --- Compute SubCircuit positions ---
    COL_GAP: int = 200
    ROW_GAP: int = 20
    LAYOUT_W: int = 120
    X_START: int = 100

    inst_positions: dict[str, tuple[int, int]] = {}
    inst_heights: dict[str, int] = {}
    used_positions: set[tuple[int, int]] = set()

    for depth in sorted(columns.keys()):
        col_x: int = X_START + depth * (LAYOUT_W + COL_GAP)
        col_y: int = 0
        for idx, inst in enumerate(columns[depth]):
            sub_c: verilog_parser.Module = mod_map[inst.module_name]
            n_max: int = max(len(sub_c.inputs), len(sub_c.outputs), 1)
            h: int = 20 * n_max + 20
            # Per-instance y-jitter to stagger pins across columns
            jitter: int = (idx % 3) * 7
            inst_positions[inst.inst_name] = (col_x, col_y + jitter)
            inst_heights[inst.inst_name] = h
            col_y += h + ROW_GAP + jitter

    # --- Place top-level Inputs ---
    cv_inputs: list[CompDict] = []
    IO_MARGIN: int = 80

    for p in top_mod.inputs:
        net: str = p.name
        bw: str | int = str(p.width) if p.width > 1 else 1
        consumers: list[str] = net_consumers.get(net, [])
        if consumers:
            min_x: int = min(inst_positions[c][0] for c in consumers
                             if c in inst_positions)
            target_y: int | None = None
            for c in consumers:
                if c not in inst_positions:
                    continue
                ci: verilog_parser.Instance = inst_by_name[c]
                pins: dict[str, dict[str, Any]] = scope_pins[ci.module_name]
                for port_name, net_expr in ci.connections.items():
                    n: str = re.sub(r'\[.*?\]', '', net_expr).strip()
                    if n == net and port_name in pins:
                        cx: int
                        cy: int
                        cx, cy = inst_positions[c]
                        target_y = cy + pins[port_name]["y"]
                        break
                if target_y is not None:
                    break
            ix: int = min_x - IO_MARGIN
            iy: int = target_y if target_y is not None else 0
        else:
            ix = X_START - IO_MARGIN
            iy = len(cv_inputs) * 40
        ix, iy = unique_pos(ix, iy, used_positions)

        out_node: int = na.alloc(10, 0, 1, p.width)
        cv_inputs.append(CompDict(
            x=ix, y=iy,
            objectType="Input", label=p.name,
            direction="RIGHT", labelDirection="LEFT",
            propagationDelay=0,
            customData=CVCustomData(
                constructorParamaters=["RIGHT", bw,
                    {"x": 0, "y": 20, "id": f"main_{p.name}"}],
                nodes={"output1": out_node},
                values={"state": 0},
            ),
        ))
        _register_net(p.name, out_node)

    # --- Place top-level Outputs ---
    cv_outputs: list[CompDict] = []

    for p in top_mod.outputs:
        net = p.name
        bw = str(p.width) if p.width > 1 else 1
        producer_name: str | None = net_producer.get(net)
        if producer_name and producer_name in inst_positions:
            pi: verilog_parser.Instance = inst_by_name[producer_name]
            pins_o: dict[str, dict[str, Any]] = scope_pins[pi.module_name]
            px: int
            py: int
            px, py = inst_positions[producer_name]
            ox: int = px + LAYOUT_W + IO_MARGIN
            target_y_o: int = py
            for port_name, net_expr in pi.connections.items():
                n = re.sub(r'\[.*?\]', '', net_expr).strip()
                if n == net and port_name in pins_o:
                    target_y_o = py + pins_o[port_name]["y"]
                    break
            oy: int = target_y_o
        else:
            max_depth: int = max(columns.keys()) if columns else 0
            ox = X_START + (max_depth + 1) * (LAYOUT_W + COL_GAP)
            oy = len(cv_outputs) * 40
        ox, oy = unique_pos(ox, oy, used_positions)

        inp_node: int = na.alloc(-10, 0, 0, p.width)
        cv_outputs.append(CompDict(
            x=ox, y=oy,
            objectType="Output", label=p.name,
            direction="LEFT", labelDirection="RIGHT",
            propagationDelay=0,
            customData=CVCustomData(
                constructorParamaters=["LEFT", bw,
                    {"x": 0, "y": 20, "id": f"main_{p.name}"}],
                nodes={"inp1": inp_node},
            ),
        ))
        _register_net(p.name, inp_node)

    # --- Place SubCircuit instances ---
    cv_subcircuits: list[dict[str, Any]] = []

    for inst in sorted_insts:
        sub_sc: verilog_parser.Module = mod_map[inst.module_name]
        sid_sc: str = scope_ids[inst.module_name]
        pins_sc: dict[str, dict[str, Any]] = scope_pins[inst.module_name]
        sx: int
        sy: int
        sx, sy = inst_positions[inst.inst_name]

        input_nodes: list[int] = []
        output_nodes: list[int] = []

        for p in sub_sc.inputs:
            pin: dict[str, Any] = pins_sc.get(p.name, {"x": 0, "y": 20})
            nid: int = na.alloc(pin["x"], pin["y"], 0, p.width)
            input_nodes.append(nid)
            net_expr_i: str = inst.connections.get(p.name, "")
            _register_net(net_expr_i, nid)

        for p in sub_sc.outputs:
            pin = pins_sc.get(p.name, {"x": LAYOUT_W, "y": 20})
            nid = na.alloc(pin["x"], pin["y"], 1, p.width)
            output_nodes.append(nid)
            net_expr_o: str = inst.connections.get(p.name, "")
            _register_net(net_expr_o, nid)

        cv_subcircuits.append({
            "x": sx, "y": sy,
            "id": sid_sc,
            "label": inst.inst_name,
            "labelDirection": "RIGHT",
            "inputNodes": input_nodes,
            "outputNodes": output_nodes,
            "version": "2.0",
        })

    # --- Wire nodes sharing the same net — chain topology ---
    for net_name, node_ids in net_nodes.items():
        for i in range(len(node_ids) - 1):
            na.connect(node_ids[i], node_ids[i + 1])

    wired_ids: list[int] = sorted(set(
        nid for ids in net_nodes.values() if len(ids) > 1 for nid in ids
    ))

    _ser = CompDict.to_dict
    result: dict[str, Any] = {
        "layout": _cv_layout(len(top_mod.inputs), len(top_mod.outputs)),
        "verilogMetadata": {
            "isVerilogCircuit": False,
            "isMainCircuit": True,
            "code": "",
            "subCircuitScopeIds": list(scope_ids.values()),
        },
        "allNodes": na.nodes_as_dicts(),
        "id": int(_cv_scope_id()),
        "name": top_mod.name,
        "Input": [_ser(c) for c in cv_inputs],
        "Output": [_ser(c) for c in cv_outputs],
        "SubCircuit": cv_subcircuits,
        "restrictedCircuitElementsUsed": [],
        "nodes": wired_ids,
        "scopes": scopes,
        "logixClipBoardData": True,
    }
    return result
