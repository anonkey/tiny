"""CircuitVerse scope ID allocator, layout, and scope builder."""

from cv_node_alloc import _CVNodeAlloc


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
