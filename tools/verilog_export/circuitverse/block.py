"""CircuitVerse JSON generation (block-level)."""

import re

from cv_node_alloc import _CVNodeAlloc
from cv_scope import _cv_scope_id, _cv_layout, _build_cv_scope
from cv_emit import unique_pos


def generate_circuitverse(top_mod, sub_modules):
    """Generate a CircuitVerse-compatible JSON dict.

    Top-level ports become Input/Output components. Each unique submodule
    type gets a scope definition. Instances become SubCircuit components
    wired together via allNodes connections.
    """
    _cv_scope_id.reset()
    na = _CVNodeAlloc()
    mod_map = {m.name: m for m in sub_modules}

    # --- Build subcircuit scopes ---
    scope_ids = {}    # module_name -> scope_id
    scope_pins = {}   # module_name -> {port_name: {x, y}}
    scopes = []
    seen = set()
    for inst in top_mod.instances:
        if inst.module_name in seen or inst.module_name not in mod_map:
            continue
        seen.add(inst.module_name)
        sub = mod_map[inst.module_name]
        scope, sid, pins = _build_cv_scope(sub, na)
        scope_ids[inst.module_name] = sid
        scope_pins[inst.module_name] = pins
        scopes.append(scope)

    # --- Net map: net_name -> list of node IDs (to connect later) ---
    net_nodes = {}

    def _register_net(net_name, node_id):
        net = re.sub(r'\[.*?\]', '', net_name).strip()
        if not net:
            return
        net_nodes.setdefault(net, []).append(node_id)

    # --- Topological sort of instances for left-to-right data flow ---
    inst_list = []
    for inst in top_mod.instances:
        sub = mod_map.get(inst.module_name)
        if sub and inst.module_name in scope_ids:
            inst_list.append(inst)

    net_producer = {}   # net_name -> inst_name
    net_consumers = {}  # net_name -> [inst_name, ...]

    for inst in inst_list:
        sub = mod_map[inst.module_name]
        port_dir = {p.name: p.direction for p in sub.ports}
        for port_name, net_expr in inst.connections.items():
            net = re.sub(r'\[.*?\]', '', net_expr).strip()
            if not net:
                continue
            d = port_dir.get(port_name, "input")
            if d == "output":
                net_producer[net] = inst.inst_name
            else:
                net_consumers.setdefault(net, []).append(inst.inst_name)

    # Compute depth
    inst_depth = {}
    inst_by_name = {inst.inst_name: inst for inst in inst_list}

    def _get_depth(iname, visiting=None):
        if iname in inst_depth:
            return inst_depth[iname]
        if visiting is None:
            visiting = set()
        if iname in visiting:
            return 0
        visiting.add(iname)
        inst = inst_by_name[iname]
        sub = mod_map[inst.module_name]
        port_dir = {p.name: p.direction for p in sub.ports}
        max_dep = 0
        for port_name, net_expr in inst.connections.items():
            net = re.sub(r'\[.*?\]', '', net_expr).strip()
            d = port_dir.get(port_name, "input")
            if d == "input" and net in net_producer:
                producer = net_producer[net]
                if producer != iname:
                    max_dep = max(max_dep, _get_depth(producer, visiting) + 1)
        inst_depth[iname] = max_dep
        return max_dep

    for inst in inst_list:
        _get_depth(inst.inst_name)

    sorted_insts = sorted(inst_list, key=lambda i: (inst_depth[i.inst_name],
                                                     inst_list.index(i)))

    columns = {}
    for inst in sorted_insts:
        d = inst_depth[inst.inst_name]
        columns.setdefault(d, []).append(inst)

    # --- Compute SubCircuit positions ---
    COL_GAP = 200
    ROW_GAP = 20
    LAYOUT_W = 120
    X_START = 100

    inst_positions = {}
    inst_heights = {}
    used_positions = set()

    for depth in sorted(columns.keys()):
        col_x = X_START + depth * (LAYOUT_W + COL_GAP)
        col_y = 0
        for idx, inst in enumerate(columns[depth]):
            sub = mod_map[inst.module_name]
            n_max = max(len(sub.inputs), len(sub.outputs), 1)
            h = 20 * n_max + 20
            # Per-instance y-jitter to stagger pins across columns
            jitter = (idx % 3) * 7
            inst_positions[inst.inst_name] = (col_x, col_y + jitter)
            inst_heights[inst.inst_name] = h
            col_y += h + ROW_GAP + jitter

    # --- Place top-level Inputs ---
    cv_inputs = []
    IO_MARGIN = 80

    for p in top_mod.inputs:
        net = p.name
        bw = str(p.width) if p.width > 1 else 1
        consumers = net_consumers.get(net, [])
        if consumers:
            min_x = min(inst_positions[c][0] for c in consumers
                        if c in inst_positions)
            target_y = None
            for c in consumers:
                if c not in inst_positions:
                    continue
                ci = inst_by_name[c]
                pins = scope_pins[ci.module_name]
                for port_name, net_expr in ci.connections.items():
                    n = re.sub(r'\[.*?\]', '', net_expr).strip()
                    if n == net and port_name in pins:
                        cx, cy = inst_positions[c]
                        target_y = cy + pins[port_name]["y"]
                        break
                if target_y is not None:
                    break
            ix = min_x - IO_MARGIN
            iy = target_y if target_y is not None else 0
        else:
            ix = X_START - IO_MARGIN
            iy = len(cv_inputs) * 40
        ix, iy = unique_pos(ix, iy, used_positions)

        out_node = na.alloc(10, 0, 1, p.width)
        cv_inputs.append({
            "x": ix, "y": iy,
            "objectType": "Input",
            "label": p.name,
            "direction": "RIGHT",
            "labelDirection": "LEFT",
            "propagationDelay": 0,
            "customData": {
                "nodes": {"output1": out_node},
                "values": {"state": 0},
                "constructorParamaters": ["RIGHT", bw,
                    {"x": 0, "y": 20, "id": f"main_{p.name}"}],
            },
        })
        _register_net(p.name, out_node)

    # --- Place top-level Outputs ---
    cv_outputs = []

    for p in top_mod.outputs:
        net = p.name
        bw = str(p.width) if p.width > 1 else 1
        producer = net_producer.get(net)
        if producer and producer in inst_positions:
            pi = inst_by_name[producer]
            pins = scope_pins[pi.module_name]
            px, py = inst_positions[producer]
            ox = px + LAYOUT_W + IO_MARGIN
            target_y = py
            for port_name, net_expr in pi.connections.items():
                n = re.sub(r'\[.*?\]', '', net_expr).strip()
                if n == net and port_name in pins:
                    target_y = py + pins[port_name]["y"]
                    break
            oy = target_y
        else:
            max_depth = max(columns.keys()) if columns else 0
            ox = X_START + (max_depth + 1) * (LAYOUT_W + COL_GAP)
            oy = len(cv_outputs) * 40
        ox, oy = unique_pos(ox, oy, used_positions)

        inp_node = na.alloc(-10, 0, 0, p.width)
        cv_outputs.append({
            "x": ox, "y": oy,
            "objectType": "Output",
            "label": p.name,
            "direction": "LEFT",
            "labelDirection": "RIGHT",
            "propagationDelay": 0,
            "customData": {
                "nodes": {"inp1": inp_node},
                "constructorParamaters": ["LEFT", bw,
                    {"x": 0, "y": 20, "id": f"main_{p.name}"}],
            },
        })
        _register_net(p.name, inp_node)

    # --- Place SubCircuit instances ---
    cv_subcircuits = []

    for inst in sorted_insts:
        sub = mod_map[inst.module_name]
        sid = scope_ids[inst.module_name]
        pins = scope_pins[inst.module_name]
        sx, sy = inst_positions[inst.inst_name]

        input_nodes = []
        output_nodes = []

        for p in sub.inputs:
            pin = pins.get(p.name, {"x": 0, "y": 20})
            nid = na.alloc(pin["x"], pin["y"], 0, p.width)
            input_nodes.append(nid)
            net_expr = inst.connections.get(p.name, "")
            _register_net(net_expr, nid)

        for p in sub.outputs:
            pin = pins.get(p.name, {"x": LAYOUT_W, "y": 20})
            nid = na.alloc(pin["x"], pin["y"], 1, p.width)
            output_nodes.append(nid)
            net_expr = inst.connections.get(p.name, "")
            _register_net(net_expr, nid)

        cv_subcircuits.append({
            "x": sx, "y": sy,
            "id": sid,
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

    wired_ids = sorted(set(
        nid for ids in net_nodes.values() if len(ids) > 1 for nid in ids
    ))

    result = {
        "layout": _cv_layout(len(top_mod.inputs), len(top_mod.outputs)),
        "verilogMetadata": {
            "isVerilogCircuit": False,
            "isMainCircuit": True,
            "code": "",
            "subCircuitScopeIds": list(scope_ids.values()),
        },
        "allNodes": na.nodes,
        "id": int(_cv_scope_id()),
        "name": top_mod.name,
        "Input": cv_inputs,
        "Output": cv_outputs,
        "SubCircuit": cv_subcircuits,
        "restrictedCircuitElementsUsed": [],
        "nodes": wired_ids,
        "scopes": scopes,
        "logixClipBoardData": True,
    }
    return result
