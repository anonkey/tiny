"""Arithmetic cells: $add, $sub, $mul, $div, $mod, $neg."""

from components._common import (
  CELL_MARGIN, _new_bus_pin, _param_int, _adapt_width,
)
from cv_common import emit_constant, emit_not_gate, emit_zero_extend, register_bits
from cv_component_registry import pin_pos, component_height


def place_add(cell_name, cell, conns, na, bit_nodes, components, x, y):
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
    components.setdefault("Splitter", []).append({
      "x": x + 60, "y": y,
      "objectType": "Splitter",
      "label": "",
      "direction": "LEFT",
      "labelDirection": "RIGHT",
      "propagationDelay": 10,
      "customData": {
        "constructorParamaters": ["LEFT", y_bw, [op_bw, 1]],
        "nodes": {"outputs": [spl_sum, spl_carry], "inp1": spl_inp},
      },
    })
  else:
    register_bits(na, bit_nodes, conns["Y"][:op_bw], sum_node, op_bw)

  comp = {
    "x": x, "y": y,
    "objectType": "Adder",
    "label": "",
    "direction": "RIGHT",
    "labelDirection": "LEFT",
    "propagationDelay": 100,
    "customData": {
      "constructorParamaters": ["RIGHT", op_bw],
      "nodes": {
        "inpA": a_node,
        "inpB": b_node,
        "carryIn": carry_in,
        "sum": sum_node,
        "carryOut": carry_out,
      },
    },
  }
  components.setdefault("Adder", []).append(comp)
  return component_height("Adder") + CELL_MARGIN + eh


def place_sub(cell_name, cell, conns, na, bit_nodes, components, x, y):
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

  ctrl_comp, ctrl_out = emit_constant(na, bit_nodes, "110", 3,
                                       x - 60, y - 50)
  components.setdefault("ConstantVal", []).append(ctrl_comp)

  c_x, c_y = pin_pos("ALU", "controlSignalInput")
  o_x, o_y = pin_pos("ALU", "output")
  co_x, co_y = pin_pos("ALU", "carryOut")
  ctrl_in = na.alloc(c_x, c_y, 0, 3)
  na.connect(ctrl_out, ctrl_in)
  out_node = na.alloc(o_x, o_y, 1, op_bw)
  carry_out = na.alloc(co_x, co_y, 1, 1)
  register_bits(na, bit_nodes, conns["Y"], out_node, y_bw)

  comp = {
    "x": x, "y": y,
    "objectType": "ALU",
    "label": "",
    "direction": "RIGHT",
    "labelDirection": "LEFT",
    "propagationDelay": 100,
    "customData": {
      "constructorParamaters": ["RIGHT", op_bw],
      "nodes": {
        "inp1": a_node,
        "inp2": b_node,
        "controlSignalInput": ctrl_in,
        "output": out_node,
        "carryOut": carry_out,
      },
    },
  }
  components.setdefault("ALU", []).append(comp)
  return component_height("ALU") + CELL_MARGIN + eh


def place_mul(cell_name, cell, conns, na, bit_nodes, components, x, y):
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

  comp = {
    "x": x, "y": y,
    "objectType": "verilogMultiplier",
    "label": "",
    "direction": "RIGHT",
    "labelDirection": "LEFT",
    "propagationDelay": 100,
    "customData": {
      "constructorParamaters": ["RIGHT", op_bw, y_bw],
      "nodes": {
        "inpA": a_node,
        "inpB": b_node,
        "product": prod_node,
      },
    },
  }
  components.setdefault("verilogMultiplier", []).append(comp)
  return component_height("verilogMultiplier") + CELL_MARGIN + eh


def place_divmod(cell_name, cell, conns, na, bit_nodes, components, x, y):
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

  comp = {
    "x": x, "y": y,
    "objectType": "verilogDivider",
    "label": "",
    "direction": "RIGHT",
    "labelDirection": "LEFT",
    "propagationDelay": 100,
    "customData": {
      "constructorParamaters": ["RIGHT", op_bw, y_bw],
      "nodes": {
        "inpA": a_node,
        "inpB": b_node,
        "quotient": quot_node,
        "remainder": rem_node,
      },
    },
  }
  components.setdefault("verilogDivider", []).append(comp)
  return component_height("verilogDivider") + CELL_MARGIN + eh


def place_neg(cell_name, cell, conns, na, bit_nodes, components, x, y):
  """Place a negation ($neg) via TwoComplement. Returns y-advance."""
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  y_bw = _param_int(cell, "Y_WIDTH", len(conns["Y"]))
  op_bw = max(a_bw, y_bw)

  i_x, i_y = pin_pos("TwoComplement", "inp1")
  o_x, o_y = pin_pos("TwoComplement", "output1")

  if a_bw == op_bw:
    inp_node = _new_bus_pin(na, bit_nodes, conns["A"], 0, a_bw, rx=i_x, ry=i_y)
  else:
    ext_comps, inp_narrow, inp_node = emit_zero_extend(
      na, bit_nodes, a_bw, op_bw, x - 80, y)
    register_bits(na, bit_nodes, conns["A"], inp_narrow, a_bw)
    for c in ext_comps:
      components.setdefault(c["objectType"], []).append(c)

  out_node = na.alloc(o_x, o_y, 1, op_bw)
  register_bits(na, bit_nodes, conns["Y"], out_node, y_bw)

  comp = {
    "x": x, "y": y,
    "objectType": "TwoComplement",
    "label": "",
    "direction": "RIGHT",
    "labelDirection": "LEFT",
    "propagationDelay": 100,
    "customData": {
      "constructorParamaters": ["RIGHT", op_bw],
      "nodes": {"inp1": inp_node, "output1": out_node},
    },
  }
  components.setdefault("TwoComplement", []).append(comp)
  return component_height("TwoComplement") + CELL_MARGIN
