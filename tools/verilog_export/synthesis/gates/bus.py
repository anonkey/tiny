"""Bus operations: $slice, $concat, $cv_splitter."""

from __future__ import annotations


from common.constants import pin_clearance, splitter_pin, _new_bus_pin, _param_int
from common.emit import emit_splitter, register_bits
from common.node_alloc import _CVNodeAlloc
from common.types import BitNodes, CompMap, YosysCell, YosysConns
from synthesis.gates.registry import dimensions as _dimensions


def _splitter_y_offset(groups: list[int]) -> int:
  """Extra downward offset so a large Splitter doesn't overlap the previous cell.

  The placement loop passes y as the component center.  Small components
  (up <= 30) fit inside the default clearance, but Splitters with many
  output groups extend further above the anchor.  Return the extra pixels
  the anchor must be pushed down.
  """
  up = _dimensions("Splitter", bitWidthSplit=groups)["up"]
  # 30 is the implicit half-height the old hardcoded '60' assumed
  return max(0, up - 30)


def place_slice(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a bus slice ($slice). Returns y-advance."""
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  y_bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))
  offset = _param_int(cell, "OFFSET", 0)

  groups = []
  if offset > 0:
    groups.append(offset)
  groups.append(y_bw)
  remaining = a_bw - offset - y_bw
  if remaining > 0:
    groups.append(remaining)

  dy = _splitter_y_offset(groups)
  y += dy

  spl_inp = _new_bus_pin(na, bit_nodes, conns["A"], 0, a_bw, rx=-10, ry=0)

  out_nodes = []
  if offset > 0:
    out_nodes.append(na.alloc(20, -10, 1, offset))
  result_out = na.alloc(20, 0, 1, y_bw)
  register_bits(na, bit_nodes, conns["Y"], result_out, y_bw)
  out_nodes.append(result_out)
  if remaining > 0:
    out_nodes.append(na.alloc(20, 10, 1, remaining))

  spl_comp, _, _ = emit_splitter(
    na, a_bw, groups, "RIGHT", x, y,
    inp_node=spl_inp, out_nodes=out_nodes)
  components.setdefault("Splitter", []).append(spl_comp)
  return dy + 60 + pin_clearance(max(1, len(groups)))


def place_concat(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a bus concat ($concat). Returns y-advance."""
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  y_bw = a_bw + b_bw

  dy = _splitter_y_offset([a_bw, b_bw])
  y += dy

  # LEFT splitter: x mirrored, so multi-pin side uses rx=20, bus side uses rx=-10
  rx_a, ry_a, nt_a = splitter_pin("LEFT", "outputs", 2, 0)
  rx_b, ry_b, nt_b = splitter_pin("LEFT", "outputs", 2, 1)
  spl_out_a = _new_bus_pin(na, bit_nodes, conns["A"], nt_a, a_bw, rx=rx_a, ry=ry_a)
  spl_out_b = _new_bus_pin(na, bit_nodes, conns["B"], nt_b, b_bw, rx=rx_b, ry=ry_b)
  irx, iry, int_ = splitter_pin("LEFT", "inp1", 2)
  spl_inp = na.alloc(irx, iry, int_, y_bw)
  register_bits(na, bit_nodes, conns["Y"], spl_inp, y_bw)

  spl_comp, _, _ = emit_splitter(
    na, y_bw, [a_bw, b_bw], "LEFT", x, y,
    inp_node=spl_inp, out_nodes=[spl_out_a, spl_out_b])
  components.setdefault("Splitter", []).append(spl_comp)
  return dy + 60 + pin_clearance(2)


def place_cv_splitter(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a synthetic $cv_splitter inserted by splitter_pass. Returns y-advance."""
  params = cell["parameters"]
  bw = params["BW"]
  direction = params["DIRECTION"]
  groups = params["GROUPS"]
  n = len(groups)

  dy = _splitter_y_offset(groups)
  y += dy

  if direction == "LEFT":
    # Joiner: N narrow inputs -> 1 wide output
    # Component has direction=LEFT so x is mirrored in set_parent_pos.
    # Multi-pin side (outputs in CV terms) must use rx=20 -> mirrors to left.
    # Bus side (inp1 in CV terms) must use rx=-10 -> mirrors to right.
    out_nodes = []
    for idx, gw in enumerate(groups):
      pn = f"I{idx}"
      orx, ory, ont = splitter_pin("LEFT", "outputs", n, idx)
      out_nodes.append(_new_bus_pin(na, bit_nodes, conns[pn], ont, gw,
                                    rx=orx, ry=ory))
    irx, iry, int_ = splitter_pin("LEFT", "inp1", n)
    inp_node = na.alloc(irx, iry, int_, bw)
    register_bits(na, bit_nodes, conns["O"], inp_node, bw)
  else:
    # Fan-out: 1 wide input -> N narrow outputs
    irx, iry, int_ = splitter_pin("RIGHT", "inp1", n)
    inp_node = _new_bus_pin(na, bit_nodes, conns["I"], int_, bw,
                            rx=irx, ry=iry)
    out_nodes = []
    for idx, gw in enumerate(groups):
      pn = f"O{idx}"
      orx, ory, ont = splitter_pin("RIGHT", "outputs", n, idx)
      nid = na.alloc(orx, ory, ont, gw)
      register_bits(na, bit_nodes, conns[pn], nid, gw)
      out_nodes.append(nid)

  spl_comp, _, _ = emit_splitter(
    na, bw, groups, direction, x, y,
    inp_node=inp_node, out_nodes=out_nodes)
  components.setdefault("Splitter", []).append(spl_comp)
  return dy + 60 + pin_clearance(n)
