"""Arithmetic cells: $add, $sub, $mul, $div, $mod, $neg."""

from __future__ import annotations

from typing import Any

from common.constants import (
  pin_clearance, _new_bus_pin, _param_int, _adapt_width, _adapt_single,
  _append_comp,
)
from common.emit import emit_alu, register_bits
from common.node_alloc import _CVNodeAlloc
from common.types import BitNodes, CompMap
from synthesis.gates.registry import pin_pos, component_height


def place_add(cell: dict[str, Any], conns: dict[str, Any], na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place an adder ($add). Returns y-advance."""
  y_bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  op_bw = max(a_bw, b_bw)

  a_node, b_node, eh = _adapt_width(
    na, bit_nodes, components, cell, op_bw, x, y)

  ci_x, ci_y = pin_pos("Adder", "carryIn")
  s_x, s_y = pin_pos("Adder", "sum")
  co_x, co_y = pin_pos("Adder", "carryOut")
  carry_in = na.alloc(ci_x, ci_y, 0, 1)
  sum_node = na.alloc(s_x, s_y, 1, op_bw)
  carry_out = na.alloc(co_x, co_y, 1, 1)

  if y_bw == op_bw:
    register_bits(na, bit_nodes, conns["Y"], sum_node, op_bw)
  elif y_bw == op_bw + 1:
    spl_inp = na.alloc(20, 10, 1, y_bw)
    spl_sum = na.alloc(-10, -10, 0, op_bw)
    spl_carry = na.alloc(-10, 10, 0, 1)
    na.connect(sum_node, spl_sum)
    na.connect(carry_out, spl_carry)
    register_bits(na, bit_nodes, conns["Y"], spl_inp, y_bw)
    _append_comp(components, "Splitter", x + 60, y,
      ["LEFT", y_bw, [op_bw, 1]],
      {"outputs": [spl_sum, spl_carry], "inp1": spl_inp},
      direction="LEFT", propagation_delay=10)
  else:
    register_bits(na, bit_nodes, conns["Y"][:op_bw], sum_node, op_bw)

  _append_comp(components, "Adder", x, y,
    ["RIGHT", op_bw],
    {"inpA": a_node, "inpB": b_node, "carryIn": carry_in,
     "sum": sum_node, "carryOut": carry_out})
  return component_height("Adder") + pin_clearance(3) + eh


def place_sub(cell: dict[str, Any], conns: dict[str, Any], na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a subtractor ($sub) via ALU mode 110. Returns y-advance."""
  y_bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  op_bw = max(a_bw, b_bw, y_bw)

  a1_x, a1_y = pin_pos("ALU", "inp1")
  a2_x, a2_y = pin_pos("ALU", "inp2")
  a_node, b_node, eh = _adapt_width(
    na, bit_nodes, components, cell, op_bw, x, y,
    a_rx=a1_x, a_ry=a1_y, b_rx=a2_x, b_ry=a2_y)

  out_node, carry_out = emit_alu(na, bit_nodes, components, op_bw, "110",
                                  x, y, a_node, b_node)
  register_bits(na, bit_nodes, conns["Y"], out_node, y_bw)
  return component_height("ALU") + pin_clearance(2) + eh


def place_mul(cell: dict[str, Any], conns: dict[str, Any], na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a multiplier ($mul). Returns y-advance."""
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  y_bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))
  op_bw = max(a_bw, b_bw)

  ma_x, ma_y = pin_pos("verilogMultiplier", "inpA")
  mb_x, mb_y = pin_pos("verilogMultiplier", "inpB")
  a_node, b_node, eh = _adapt_width(
    na, bit_nodes, components, cell, op_bw, x, y,
    a_rx=ma_x, a_ry=ma_y, b_rx=mb_x, b_ry=mb_y)

  prod_node = na.alloc(20, 0, 1, y_bw)
  register_bits(na, bit_nodes, conns["Y"], prod_node, y_bw)

  _append_comp(components, "verilogMultiplier", x, y,
    ["RIGHT", op_bw, y_bw],
    {"inpA": a_node, "inpB": b_node, "product": prod_node})
  return component_height("verilogMultiplier") + pin_clearance(2) + eh


def place_divmod(cell: dict[str, Any], conns: dict[str, Any], na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a divider ($div/$mod). Returns y-advance."""
  ctype = cell["type"]
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  y_bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))
  op_bw = max(a_bw, b_bw)

  da_x, da_y = pin_pos("verilogDivider", "inpA")
  db_x, db_y = pin_pos("verilogDivider", "inpB")
  a_node, b_node, eh = _adapt_width(
    na, bit_nodes, components, cell, op_bw, x, y,
    a_rx=da_x, a_ry=da_y, b_rx=db_x, b_ry=db_y)

  quot_node = na.alloc(20, -10, 1, y_bw)
  rem_node = na.alloc(20, 10, 1, y_bw)
  if ctype == "$div":
    register_bits(na, bit_nodes, conns["Y"], quot_node, y_bw)
  else:
    register_bits(na, bit_nodes, conns["Y"], rem_node, y_bw)

  _append_comp(components, "verilogDivider", x, y,
    ["RIGHT", op_bw, y_bw],
    {"inpA": a_node, "inpB": b_node, "quotient": quot_node,
     "remainder": rem_node})
  return component_height("verilogDivider") + pin_clearance(2) + eh


def place_neg(cell: dict[str, Any], conns: dict[str, Any], na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a negation ($neg) via TwoComplement. Returns y-advance."""
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  y_bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))
  op_bw = max(a_bw, y_bw)

  i_x, i_y = pin_pos("TwoComplement", "inp1")
  o_x, o_y = pin_pos("TwoComplement", "output1")

  inp_node, _ = _adapt_single(na, bit_nodes, components,
    conns["A"], a_bw, op_bw, x, y, rx=i_x, ry=i_y)

  out_node = na.alloc(o_x, o_y, 1, op_bw)
  register_bits(na, bit_nodes, conns["Y"], out_node, y_bw)

  _append_comp(components, "TwoComplement", x, y,
    ["RIGHT", op_bw], {"inp1": inp_node, "output1": out_node})
  return component_height("TwoComplement") + pin_clearance(1)
