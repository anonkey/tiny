"""Bus operations: $slice, $concat, $cv_splitter."""

from __future__ import annotations


from common.constants import pin_clearance, _new_bus_pin, _param_int
from common.emit import emit_splitter, register_bits
from common.node_alloc import _CVNodeAlloc
from common.types import BitNodes, CompMap, YosysCell, YosysConns


def place_slice(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
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


def place_concat(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a bus concat ($concat). Returns y-advance."""
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  y_bw = a_bw + b_bw

  # LEFT splitter: x mirrored, so multi-pin side uses rx=20, bus side uses rx=-10
  y_offset = int((2 / 2 - 1) * 20)  # n=2 groups
  spl_out_a = _new_bus_pin(na, bit_nodes, conns["A"], 0, a_bw, rx=20, ry=0 * 20 - y_offset - 20)
  spl_out_b = _new_bus_pin(na, bit_nodes, conns["B"], 0, b_bw, rx=20, ry=1 * 20 - y_offset - 20)
  spl_inp = na.alloc(-10, 10 + y_offset, 1, y_bw)
  register_bits(na, bit_nodes, conns["Y"], spl_inp, y_bw)

  spl_comp, _, _ = emit_splitter(
    na, y_bw, [a_bw, b_bw], "LEFT", x, y,
    inp_node=spl_inp, out_nodes=[spl_out_a, spl_out_b])
  components.setdefault("Splitter", []).append(spl_comp)
  return 60 + pin_clearance(2)


def place_cv_splitter(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a synthetic $cv_splitter inserted by splitter_pass. Returns y-advance."""
  params = cell["parameters"]
  bw = params["BW"]
  direction = params["DIRECTION"]
  groups = params["GROUPS"]
  n = len(groups)

  if direction == "LEFT":
    # Joiner: N narrow inputs -> 1 wide output
    # Component has direction=LEFT so x is mirrored in set_parent_pos.
    # Multi-pin side (outputs in CV terms) must use rx=20 -> mirrors to left.
    # Bus side (inp1 in CV terms) must use rx=-10 -> mirrors to right.
    y_offset = int((n / 2 - 1) * 20)
    out_nodes = []
    for idx, gw in enumerate(groups):
      pn = f"I{idx}"
      out_nodes.append(_new_bus_pin(na, bit_nodes, conns[pn], 0, gw,
                                    rx=20, ry=idx * 20 - y_offset - 20))
    inp_node = na.alloc(-10, 10 + y_offset, 1, bw)
    register_bits(na, bit_nodes, conns["O"], inp_node, bw)
  else:
    # Fan-out: 1 wide input -> N narrow outputs
    inp_node = _new_bus_pin(na, bit_nodes, conns["I"], 0, bw,
                            rx=-10, ry=(bw - 1) * 10)
    out_nodes = []
    for idx, gw in enumerate(groups):
      pn = f"O{idx}"
      y_offset = int((n / 2 - 1) * 20)
      nid = na.alloc(20, idx * 20 - y_offset - 20, 1, gw)
      register_bits(na, bit_nodes, conns[pn], nid, gw)
      out_nodes.append(nid)

  spl_comp, _, _ = emit_splitter(
    na, bw, groups, direction, x, y,
    inp_node=inp_node, out_nodes=out_nodes)
  components.setdefault("Splitter", []).append(spl_comp)
  return 60 + pin_clearance(n)
