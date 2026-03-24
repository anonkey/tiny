"""Reduction and logic operations: $reduce_*, $logic_not, $logic_and, $logic_or."""

from circuitverse.components._common import (
  CELL_GAP, pin_clearance, _new_bus_pin, _param_int,
)
from cv_emit import emit_split_reduce, register_bits
from circuitverse.components.registry import pin_pos, gate_output_pos, component_height


def place_reduce(cell_name, cell, conns, na, bit_nodes, components, x, y):
  """Place a reduction op ($reduce_and/or/xor/xnor/bool). Returns y-advance."""
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  reduce_map = {
    "$reduce_and": "AndGate",
    "$reduce_or": "OrGate",
    "$reduce_xor": "XorGate",
    "$reduce_xnor": "XnorGate",
    "$reduce_bool": "OrGate",
  }
  gate_type = reduce_map[cell["type"]]

  spl_inp = _new_bus_pin(na, bit_nodes, conns["A"], 0, a_bw, rx=-10, ry=0)
  gate_out = emit_split_reduce(
    na, bit_nodes, components, a_bw, spl_inp,
    gate_type, x - 40, y, x + 40, y)
  register_bits(na, bit_nodes, conns["Y"], gate_out, 1)
  return component_height(gate_type, inputLength=a_bw) + pin_clearance(1)


def place_logic_not(cell_name, cell, conns, na, bit_nodes, components, x, y):
  """Place $logic_not (NOR reduction). Returns y-advance."""
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  spl_inp = _new_bus_pin(na, bit_nodes, conns["A"], 0, a_bw, rx=-10, ry=0)
  gate_out = emit_split_reduce(
    na, bit_nodes, components, a_bw, spl_inp,
    "NorGate", x - 60, y, x + 20, y)
  register_bits(na, bit_nodes, conns["Y"], gate_out, 1)
  return component_height("NorGate", inputLength=a_bw) + pin_clearance(1)


def place_logic_and_or(cell_name, cell, conns, na, bit_nodes, components, x, y):
  """Place $logic_and or $logic_or. Returns y-advance."""
  ctype = cell["type"]
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))

  def _reduce_to_bool(bits, bw, x_off, y_off):
    if bw == 1:
      return _new_bus_pin(na, bit_nodes, bits, 0, 1, rx=-20, ry=0)
    spl_inp = _new_bus_pin(na, bit_nodes, bits, 0, bw, rx=-10, ry=0)
    return emit_split_reduce(
      na, bit_nodes, components, bw, spl_inp,
      "OrGate", x + x_off - 60, y + y_off, x + x_off, y + y_off)

  a_bool = _reduce_to_bool(conns["A"], a_bw, -20, -20)
  b_bool = _reduce_to_bool(conns["B"], b_bw, -20, 20)

  gate_type = "AndGate" if ctype == "$logic_and" else "OrGate"
  ga_x, ga_y = pin_pos(gate_type, "inp", index=0, inputLength=2)
  gb_x, gb_y = pin_pos(gate_type, "inp", index=1, inputLength=2)
  go_x, go_y = gate_output_pos(gate_type)
  ga = na.alloc(ga_x, ga_y, 0, 1)
  gb = na.alloc(gb_x, gb_y, 0, 1)
  na.connect(a_bool, ga)
  na.connect(b_bool, gb)
  gout = na.alloc(go_x, go_y, 1, 1)
  register_bits(na, bit_nodes, conns["Y"], gout, 1)
  components.setdefault(gate_type, []).append({
    "x": x + 40, "y": y,
    "objectType": gate_type,
    "label": "",
    "direction": "RIGHT",
    "labelDirection": "LEFT",
    "propagationDelay": 100,
    "customData": {
      "constructorParamaters": ["RIGHT", 2, 1],
      "nodes": {"inp": [ga, gb], "output1": gout},
    },
  })
  return component_height(gate_type, inputLength=2) + pin_clearance(1) + 40
