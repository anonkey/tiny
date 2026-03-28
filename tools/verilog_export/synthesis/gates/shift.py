"""Shift operations: $shl, $sshl, $shr, $sshr (merged)."""

from __future__ import annotations


from common.constants import pin_clearance, _new_bus_pin, _param_int, _append_comp
from common.emit import register_bits
from common.node_alloc import _CVNodeAlloc
from common.types import BitNodes, CompMap, YosysCell, YosysConns
from synthesis.gates.registry import pin_pos, component_height


def place_shift(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a shift-left or shift-right. Returns y-advance."""
  ctype = cell["type"]
  cv_type = "verilogShiftLeft" if ctype in ("$shl", "$sshl") else "verilogShiftRight"

  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  y_bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))

  i1_x, i1_y = pin_pos(cv_type, "inp1")
  si_x, si_y = pin_pos(cv_type, "shiftInp")
  inp_a = _new_bus_pin(na, bit_nodes, conns["A"], 0, a_bw, rx=i1_x, ry=i1_y)
  inp_b = _new_bus_pin(na, bit_nodes, conns["B"], 0, b_bw, rx=si_x, ry=si_y)
  out_y = na.alloc(20, 0, 1, y_bw)
  register_bits(na, bit_nodes, conns["Y"], out_y, y_bw)

  _append_comp(components, cv_type, x, y,
    ["RIGHT", a_bw, y_bw],
    {"inp1": inp_a, "shiftInp": inp_b, "output1": out_y})
  return component_height(cv_type) + pin_clearance(2)
