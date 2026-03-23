"""High-level multi-bit logic gates: $and, $or, $xor, $xnor, $not."""

from circuitverse.components._common import (
  pin_clearance, _new_bus_pin, _param_int, _adapt_width,
)
from cv_common import emit_zero_extend, register_bits
from circuitverse.components.registry import pin_pos, gate_output_pos, component_height


def place_logic(cell_name, cell, conns, na, bit_nodes, components, x, y):
  """Place a multi-bit logic gate. Returns y-advance."""
  ctype = cell["type"]

  if ctype in ("$and", "$or", "$xor", "$xnor"):
    cv_map = {
      "$and": "AndGate", "$or": "OrGate",
      "$xor": "XorGate", "$xnor": "XnorGate",
    }
    cv_type = cv_map[ctype]
    bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))
    ia_x, ia_y = pin_pos(cv_type, "inp", index=0, inputLength=2)
    ib_x, ib_y = pin_pos(cv_type, "inp", index=1, inputLength=2)
    a_node, b_node, eh = _adapt_width(
      na, bit_nodes, components, cell, bw, x, y,
      a_rx=ia_x, a_ry=ia_y, b_rx=ib_x, b_ry=ib_y)
    ox, oy = gate_output_pos(cv_type)
    out_y = _new_bus_pin(na, bit_nodes, conns["Y"], 1, bw, rx=ox, ry=oy)
    comp = {
      "x": x, "y": y,
      "objectType": cv_type,
      "label": "",
      "direction": "RIGHT",
      "labelDirection": "LEFT",
      "propagationDelay": 100,
      "customData": {
        "constructorParamaters": ["RIGHT", 2, bw],
        "nodes": {"inp": [a_node, b_node], "output1": out_y},
      },
    }
    components.setdefault(cv_type, []).append(comp)
    return component_height(cv_type, inputLength=2) + pin_clearance(2) + eh

  # $not
  bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  if a_bw == bw:
    inp_a = _new_bus_pin(na, bit_nodes, conns["A"], 0, bw, rx=-10, ry=0)
  else:
    ext_comps, inp_narrow, inp_a = emit_zero_extend(
      na, bit_nodes, a_bw, bw, x - 80, y)
    register_bits(na, bit_nodes, conns["A"], inp_narrow, a_bw)
    for c in ext_comps:
      components.setdefault(c["objectType"], []).append(c)
  out_y = _new_bus_pin(na, bit_nodes, conns["Y"], 1, bw, rx=20, ry=0)
  comp = {
    "x": x, "y": y,
    "objectType": "NotGate",
    "label": "",
    "direction": "RIGHT",
    "labelDirection": "LEFT",
    "propagationDelay": 100,
    "customData": {
      "constructorParamaters": ["RIGHT", bw],
      "nodes": {"inp1": inp_a, "output1": out_y},
    },
  }
  components.setdefault("NotGate", []).append(comp)
  return component_height("NotGate") + pin_clearance(1)
