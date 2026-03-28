"""Comparison cells: $eq, $ne, $lt, $gt, $le, $ge."""

from __future__ import annotations


from common.constants import (
  pin_clearance, _new_bus_pin, _param_int, _adapt_width, _append_comp,
)
from common.emit import (
  emit_not_gate, emit_splitter, emit_split_reduce,
  emit_alu, register_bits,
)
from common.node_alloc import _CVNodeAlloc
from common.types import BitNodes, CompMap, YosysCell, YosysConns
from synthesis.gates.registry import pin_pos, component_height


def place_eq_ne(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place equality/inequality ($eq/$ne). Returns y-advance."""
  ctype = cell["type"]
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  op_bw = max(a_bw, b_bw)

  a_node, b_node, eh = _adapt_width(
    na, bit_nodes, components, cell, op_bw, x, y)

  # XNOR gate: bitwise compare
  xnor_out = na.alloc(20, 0, 1, op_bw)
  _append_comp(components, "XnorGate", x, y,
    ["RIGHT", 2, op_bw],
    {"inp": [a_node, b_node], "output1": xnor_out})

  # Split-reduce: AND for $eq, NAND for $ne
  reduce_type = "AndGate" if ctype == "$eq" else "NandGate"
  reduce_out = emit_split_reduce(
    na, bit_nodes, components, op_bw, xnor_out,
    reduce_type, x + 60, y, x + 120, y)
  register_bits(na, bit_nodes, conns["Y"], reduce_out, 1)

  return component_height("XnorGate", inputLength=2) + pin_clearance(2) + eh


def place_lt_gt_le_ge(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place comparison ($lt/$gt/$le/$ge) via ALU mode 111. Returns y-advance."""
  ctype = cell["type"]
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  op_bw = max(a_bw, b_bw)

  a1_x, a1_y = pin_pos("ALU", "inp1")
  a2_x, a2_y = pin_pos("ALU", "inp2")

  # For $gt and $ge, swap A and B
  if ctype in ("$gt", "$ge"):
    cell_swapped = dict(cell)
    cell_swapped["connections"] = dict(conns)
    cell_swapped["connections"]["A"] = conns["B"]
    cell_swapped["connections"]["B"] = conns["A"]
    cell_swapped["parameters"] = dict(cell.get("parameters", {}))
    cell_swapped["parameters"]["A_WIDTH"] = _param_int(cell, "B_WIDTH", b_bw)
    cell_swapped["parameters"]["B_WIDTH"] = _param_int(cell, "A_WIDTH", a_bw)
    a_node, b_node, eh = _adapt_width(
      na, bit_nodes, components, cell_swapped, op_bw, x, y,
      a_rx=a1_x, a_ry=a1_y, b_rx=a2_x, b_ry=a2_y)
  else:
    a_node, b_node, eh = _adapt_width(
      na, bit_nodes, components, cell, op_bw, x, y,
      a_rx=a1_x, a_ry=a1_y, b_rx=a2_x, b_ry=a2_y)

  # ALU with control = 111 (LESS comparison)
  alu_out, carry_out = emit_alu(na, bit_nodes, components, op_bw, "111",
                                 x, y, a_node, b_node)

  # Extract bit 0 via Splitter
  spl_comp, spl_inp, spl_outs = emit_splitter(
    na, op_bw, [1], "RIGHT", x + 60, y)
  na.connect(alu_out, spl_inp)
  components.setdefault("Splitter", []).append(spl_comp)
  bit0 = spl_outs[0]

  # For $le/$ge, invert the result
  if ctype in ("$le", "$ge"):
    not_comp, not_inp, not_out = emit_not_gate(
      na, bit_nodes, 1, x + 120, y)
    na.connect(bit0, not_inp)
    components.setdefault("NotGate", []).append(not_comp)
    register_bits(na, bit_nodes, conns["Y"], not_out, 1)
  else:
    register_bits(na, bit_nodes, conns["Y"], bit0, 1)

  return component_height("ALU") + pin_clearance(2) + eh
