"""Bus operations: $slice, $concat."""

from circuitverse.components._common import pin_clearance, _new_bus_pin, _param_int
from cv_common import emit_splitter, register_bits


def place_slice(cell_name, cell, conns, na, bit_nodes, components, x, y):
  """Place a bus slice ($slice). Returns y-advance."""
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  y_bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))
  offset = _param_int(cell, "OFFSET", 0)

  spl_inp = _new_bus_pin(na, bit_nodes, conns["A"], 0, a_bw, rx=-10, ry=0)

  groups = []
  out_nodes = []
  if offset > 0:
    groups.append(offset)
    out_nodes.append(na.alloc(20, -10, 1, offset))
  groups.append(y_bw)
  result_out = na.alloc(20, 0, 1, y_bw)
  register_bits(na, bit_nodes, conns["Y"], result_out, y_bw)
  out_nodes.append(result_out)
  remaining = a_bw - offset - y_bw
  if remaining > 0:
    groups.append(remaining)
    out_nodes.append(na.alloc(20, 10, 1, remaining))

  spl_comp, _, _ = emit_splitter(
    na, a_bw, groups, "RIGHT", x, y,
    inp_node=spl_inp, out_nodes=out_nodes)
  components.setdefault("Splitter", []).append(spl_comp)
  return 60 + pin_clearance(max(1, len(groups)))


def place_concat(cell_name, cell, conns, na, bit_nodes, components, x, y):
  """Place a bus concat ($concat). Returns y-advance."""
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  y_bw = a_bw + b_bw

  spl_out_a = _new_bus_pin(na, bit_nodes, conns["A"], 0, a_bw, rx=-10, ry=-10)
  spl_out_b = _new_bus_pin(na, bit_nodes, conns["B"], 0, b_bw, rx=-10, ry=10)
  spl_inp = na.alloc(20, 0, 1, y_bw)
  register_bits(na, bit_nodes, conns["Y"], spl_inp, y_bw)

  spl_comp, _, _ = emit_splitter(
    na, y_bw, [a_bw, b_bw], "LEFT", x, y,
    inp_node=spl_inp, out_nodes=[spl_out_a, spl_out_b])
  components.setdefault("Splitter", []).append(spl_comp)
  return 60 + pin_clearance(2)
