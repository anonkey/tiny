"""Shared CircuitVerse helpers: node allocator, scope IDs, layout, scope builder,
and common component patterns (zero-extension, polarity inversion, constants)."""

class _CVNodeAlloc:
    """Allocate sequential node IDs for CircuitVerse allNodes list."""

    def __init__(self):
        self.nodes = []  # list of node dicts
        self.abs_pos = []  # (abs_x, abs_y) for each node

    def alloc(self, x, y, ntype, bit_width, label="", parent_id=None):
        nid = len(self.nodes)
        node = {
            "x": x, "y": y,
            "type": ntype,  # 0=input, 1=output, 2=bidir
            "bitWidth": bit_width,
            "label": label,
            "connections": [],
        }
        self.nodes.append(node)
        self.abs_pos.append((0, 0))  # set later via set_parent_pos
        return nid

    def set_parent_pos(self, nid, parent_x, parent_y, direction="RIGHT"):
        """Record the absolute position of a node (parent pos + relative).

        Pin coordinates are stored in RIGHT orientation.  For LEFT-direction
        components the x axis must be mirrored so that ``abs_pos`` reflects
        the *visual* position used by the router.
        """
        n = self.nodes[nid]
        nx = -n["x"] if direction == "LEFT" else n["x"]
        self.abs_pos[nid] = (parent_x + nx, parent_y + n["y"])

    def connect(self, a, b):
        if b not in self.nodes[a]["connections"]:
            self.nodes[a]["connections"].append(b)
        if a not in self.nodes[b]["connections"]:
            self.nodes[b]["connections"].append(a)

    def verify_routing(self, components=None):
        """Check for routing issues: diagonals, visual shorts, clearance, endpoints-on-wire.

        Prints warnings to stderr.  Returns number of issues found.
        """
        from cv_verify import verify_routing as _verify
        return _verify(self.nodes, self.abs_pos, components)

    def route_orthogonal(self, components=None):
        """Insert intermediate type-2 nodes so all wires are orthogonal."""
        from cv_router import route_orthogonal as _route
        _route(self.nodes, self.abs_pos, components)


class _CVScopeCounter:
    """Sequential scope-ID allocator for CircuitVerse."""

    _SCOPE_ID_BASE = 10_000_000_000  # high base avoids collisions with CV internals

    def __init__(self):
        self._counter = -1

    def __call__(self):
        self._counter += 1
        return str(self._SCOPE_ID_BASE + self._counter)

    def reset(self):
        self._counter = -1

_cv_scope_id = _CVScopeCounter()


def _cv_layout(n_inputs, n_outputs):
    """Compute subcircuit layout block size."""
    n_max = max(n_inputs, n_outputs, 1)
    return {
        "width": 120,
        "height": 20 * n_max + 20,
        "title_x": 50,
        "title_y": 13,
        "titleEnabled": True,
    }


def _build_cv_scope(mod, na):
    """Build a CircuitVerse scope dict for a Module (subcircuit definition).

    Returns (scope_dict, scope_id, pin_positions).
    pin_positions maps port_name -> {"x": ..., "y": ...} for SubCircuit node
    placement in the parent.
    """
    scope_id = _cv_scope_id()
    sna = _CVNodeAlloc()
    layout = _cv_layout(len(mod.inputs), len(mod.outputs))
    layout_w = layout["width"]

    inputs = []
    outputs = []
    pin_positions = {}  # port_name -> {x, y} on the SubCircuit box

    pin_y = 20
    for p in mod.inputs:
        out_node = sna.alloc(10, 0, 1, p.width)
        bw = str(p.width) if p.width > 1 else 1
        pin_positions[p.name] = {"x": 0, "y": pin_y}
        inputs.append({
            "x": -20, "y": pin_y - 20,
            "objectType": "Input",
            "label": p.name,
            "direction": "RIGHT",
            "labelDirection": "LEFT",
            "propagationDelay": 0,
            "customData": {
                "nodes": {"output1": out_node},
                "values": {"state": 0},
                "constructorParamaters": [
                    "RIGHT", bw,
                    {"x": 0, "y": pin_y, "id": f"sc_{mod.name}_{p.name}"},
                ],
            },
        })
        pin_y += 20

    pin_y = 20
    for p in mod.outputs:
        inp_node = sna.alloc(-10, 0, 0, p.width)
        bw = str(p.width) if p.width > 1 else 1
        pin_positions[p.name] = {"x": layout_w, "y": pin_y}
        outputs.append({
            "x": layout_w + 20, "y": pin_y - 20,
            "objectType": "Output",
            "label": p.name,
            "direction": "LEFT",
            "labelDirection": "RIGHT",
            "propagationDelay": 0,
            "customData": {
                "nodes": {"inp1": inp_node},
                "constructorParamaters": [
                    "LEFT", bw,
                    {"x": layout_w, "y": pin_y, "id": f"sc_{mod.name}_{p.name}"},
                ],
            },
        })
        pin_y += 20

    scope = {
        "layout": layout,
        "verilogMetadata": {
            "isVerilogCircuit": False,
            "isMainCircuit": False,
            "code": "",
            "subCircuitScopeIds": [],
        },
        "allNodes": sna.nodes,
        "id": scope_id,
        "name": mod.name,
        "Input": inputs,
        "Output": outputs,
        "restrictedCircuitElementsUsed": [],
        "nodes": list(range(len(sna.nodes))),
    }
    return scope, scope_id, pin_positions


# ---------------------------------------------------------------------------
# Common component patterns used by high-level cell handlers
# ---------------------------------------------------------------------------

def emit_constant(na, bit_nodes, value_str, bw, x, y):
    """Emit a ConstantVal component.

    value_str: binary string like "00000001" (MSB first, length == bw).
    Returns (component_dict, output_node_id).
    """
    out_node = na.alloc(bw * 10, 0, 1, bw)
    comp = {
        "x": x, "y": y,
        "objectType": "ConstantVal",
        "label": "",
        "direction": "RIGHT",
        "labelDirection": "LEFT",
        "propagationDelay": 10,
        "customData": {
            "constructorParamaters": ["RIGHT", bw, value_str],
            "nodes": {"output1": out_node},
        },
    }
    return comp, out_node


def emit_not_gate(na, bit_nodes, bw, x, y):
    """Emit a NotGate component.

    Returns (component_dict, inp_node_id, out_node_id).
    """
    inp = na.alloc(-10, 0, 0, bw)
    out = na.alloc(20, 0, 1, bw)
    comp = {
        "x": x, "y": y,
        "objectType": "NotGate",
        "label": "",
        "direction": "RIGHT",
        "labelDirection": "LEFT",
        "propagationDelay": 100,
        "customData": {
            "constructorParamaters": ["RIGHT", bw],
            "nodes": {"inp1": inp, "output1": out},
        },
    }
    return comp, inp, out


def emit_zero_extend(na, bit_nodes, in_bw, out_bw, x, y):
    """Emit a Splitter + ConstantVal(0) to zero-extend a signal.

    Returns (components_list, input_node_id, output_node_id).
    Where input_node_id is the narrow input and output_node_id is the wide output.
    """
    extra = out_bw - in_bw
    comps = []

    # Splitter: groups = [in_bw, extra], direction LEFT (combining)
    spl_inp = na.alloc(20, (1) * 10, 1, out_bw)  # wide output
    spl_out0 = na.alloc(-10, -10 * 0, 0, in_bw)  # narrow input
    spl_out1 = na.alloc(-10, -10 * 0 + 20, 0, extra)  # zero padding
    comps.append({
        "x": x, "y": y,
        "objectType": "Splitter",
        "label": "",
        "direction": "LEFT",
        "labelDirection": "RIGHT",
        "propagationDelay": 10,
        "customData": {
            "constructorParamaters": ["LEFT", out_bw, [in_bw, extra]],
            "nodes": {"outputs": [spl_out0, spl_out1], "inp1": spl_inp},
        },
    })

    # ConstantVal: all zeros for the extra bits
    zero_str = "0" * extra
    zero_comp, zero_out = emit_constant(na, bit_nodes, zero_str, extra, x - 60, y + 20)
    comps.append(zero_comp)
    na.connect(zero_out, spl_out1)

    return comps, spl_out0, spl_inp


def register_bits(na, bit_nodes, bits, node_id, bw):
    """Register a multi-bit node on all its Yosys bit indices.

    For a multi-bit node, each bit index in the Yosys bits array maps to the
    same node_id. This only works when all bits belong to the same bus.
    """
    for b in bits:
        if not isinstance(b, str):
            bit_nodes.setdefault(b, []).append(node_id)


def unique_pos(x, y, used, step=20):
    """Nudge y until (x, y) is not in the used set, then register it."""
    while (x, y) in used:
        y += step
    used.add((x, y))
    return x, y


def emit_splitter(na, bw, groups, direction, x, y,
                  inp_node=None, out_nodes=None):
    """Emit a Splitter component.

    direction: "RIGHT" (fan-out / split) or "LEFT" (fan-in / join).
    groups: list of bit widths per output (e.g. [1, 1, 1] or [4, 2]).

    Returns (component_dict, inp_node, output_nodes_list).
    If inp_node/out_nodes are None, allocates with standard positions.
    """
    n = len(groups)
    if direction == "RIGHT":
        if inp_node is None:
            inp_node = na.alloc(-10, (bw - 1) * 10, 0, bw)
        if out_nodes is None:
            out_nodes = []
            for i, g in enumerate(groups):
                out_nodes.append(na.alloc(20, -10 * (n - 1) + i * 20, 1, g))
    else:
        if out_nodes is None:
            out_nodes = []
            for i, g in enumerate(groups):
                out_nodes.append(na.alloc(-10, -10 * (n - 1) + i * 20, 0, g))
        if inp_node is None:
            inp_node = na.alloc(20, (bw - 1) * 10, 1, bw)

    label_dir = "LEFT" if direction == "RIGHT" else "RIGHT"
    comp = {
        "x": x, "y": y,
        "objectType": "Splitter",
        "label": "",
        "direction": direction,
        "labelDirection": label_dir,
        "propagationDelay": 10,
        "customData": {
            "constructorParamaters": [direction, bw, groups],
            "nodes": {"outputs": out_nodes, "inp1": inp_node},
        },
    }
    return comp, inp_node, out_nodes


def emit_split_reduce(na, bit_nodes, components, bw, inp_node,
                      gate_type, spl_x, spl_y, gate_x, gate_y):
    """Split a multi-bit signal to 1-bit lines and reduce through an N-input gate.

    inp_node: the multi-bit source node (already allocated, already connected).
    gate_type: "AndGate", "OrGate", "NorGate", "XorGate", "XnorGate", "NandGate".

    Emits a Splitter + gate, appends both to components.
    Returns the 1-bit output node ID.
    """
    spl_comp, spl_inp, spl_outputs = emit_splitter(
        na, bw, [1] * bw, "RIGHT", spl_x, spl_y)
    na.connect(inp_node, spl_inp)
    components.setdefault("Splitter", []).append(spl_comp)

    from circuitverse.components.registry import pin_pos, gate_output_pos
    gate_inputs = []
    for i, spl_out in enumerate(spl_outputs):
        ix, iy = pin_pos(gate_type, "inp", index=i, inputLength=bw)
        gate_inp = na.alloc(ix, iy, 0, 1)
        na.connect(spl_out, gate_inp)
        gate_inputs.append(gate_inp)
    ox, oy = gate_output_pos(gate_type)
    gate_out = na.alloc(ox, oy, 1, 1)

    components.setdefault(gate_type, []).append({
        "x": gate_x, "y": gate_y,
        "objectType": gate_type,
        "label": "",
        "direction": "RIGHT",
        "labelDirection": "LEFT",
        "propagationDelay": 100,
        "customData": {
            "constructorParamaters": ["RIGHT", bw, 1],
            "nodes": {"inp": gate_inputs, "output1": gate_out},
        },
    })
    return gate_out


def emit_component(na, component_type, x, y, direction="RIGHT", label="",
                   propagation_delay=100, bitWidth=1, **extra_params):
    """Emit any simple component using the registry for pin positions.

    Handles components with static pins (fixed x/y in the reference).
    For components with dynamic/array pins (gates, mux), use specialized
    emitters or manual allocation.

    Returns (component_dict, {pin_name: node_id}).
    """
    from circuitverse.components.registry import _COMPONENTS, _resolve_bw, pin_pos

    comp_ref = _COMPONENTS.get(component_type)
    if comp_ref is None:
        raise KeyError(f"Unknown component: {component_type}")

    params = {"bitWidth": bitWidth, **extra_params}
    pin_nodes = {}
    nodes_dict = {}

    for pname, pinfo in comp_ref.get("pins", {}).items():
        # Skip array pins — caller must handle these
        if "count" in pinfo or "positions_formula" in pinfo:
            continue
        try:
            px, py = pin_pos(component_type, pname, **params)
        except KeyError:
            continue
        ptype = pinfo.get("type", "input")
        ntype = 0 if ptype == "input" else 1
        bw = _resolve_bw(pinfo.get("bitWidth", 1), params)
        nid = na.alloc(px, py, ntype, bw)
        pin_nodes[pname] = nid
        nodes_dict[pname] = nid

    # Build constructor params from reference
    ctor_params = [direction]
    for cp in comp_ref.get("constructor_params", []):
        cpname = cp["name"]
        if cpname == "direction":
            continue
        if cpname in params:
            ctor_params.append(params[cpname])
        elif "default" in cp and cp["default"] is not None:
            ctor_params.append(cp["default"])

    label_dir = {"RIGHT": "LEFT", "LEFT": "RIGHT",
                 "UP": "DOWN", "DOWN": "UP"}.get(direction, "LEFT")

    comp = {
        "x": x, "y": y,
        "objectType": component_type,
        "label": label,
        "direction": direction,
        "labelDirection": label_dir,
        "propagationDelay": propagation_delay,
        "customData": {
            "constructorParamaters": ctor_params,
            "nodes": nodes_dict,
        },
    }
    return comp, pin_nodes
