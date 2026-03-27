"""Gate-level (1-bit) cell placement: $_AND_, $_OR_, $_NOT_, $_MUX_, $_DFF*."""

import logging

_log = logging.getLogger(__name__)

from common.constants import (
  _YOSYS_GATE_TO_CV, _YOSYS_DFF_PREFIX, COL_GAP, X_START,
  GATE_V_CELL_PAD, pin_clearance, _new_pin, _make_comp,
)
from synthesis.gates.registry import pin_pos, gate_output_pos, component_height


def place_gate_cells(col_cells, na, bit_nodes, col_x=None, sub_scope_ids=None):
  """Place gate-level (1-bit) cells. Returns (components, cell_positions,
  cv_subcircuits, sc_comps)."""
  from placement.layout import _place_subcircuit
  components = {}
  cell_positions = {}
  cv_subcircuits = []
  sc_comps = []

  for depth in sorted(col_cells.keys()):
    x_cell = col_x.get(depth, X_START + depth * COL_GAP) if col_x else X_START + depth * COL_GAP
    y_cell = 0

    for cell_name, cell in col_cells[depth]:
      ctype = cell["type"]
      cell_positions[cell_name] = (x_cell, y_cell)

      # Subcircuit cell
      if sub_scope_ids and ctype in sub_scope_ids:
        h, n_max = _place_subcircuit(cell_name, cell, na, bit_nodes, sub_scope_ids,
                                     x_cell, y_cell, cv_subcircuits, sc_comps)
        y_cell += h + pin_clearance(n_max) + GATE_V_CELL_PAD
        continue

      cv_info = _YOSYS_GATE_TO_CV.get(ctype)

      if ctype in ("$_AND_", "$_OR_", "$_NAND_", "$_NOR_",
                    "$_XOR_", "$_XNOR_"):
        cv_type, n_inp = cv_info
        ia_x, ia_y = pin_pos(cv_type, "inp", index=0, inputLength=2)
        ib_x, ib_y = pin_pos(cv_type, "inp", index=1, inputLength=2)
        ox, oy = gate_output_pos(cv_type)
        inp_a = _new_pin(na, bit_nodes, cell["connections"]["A"][0], 0, rx=ia_x, ry=ia_y)
        inp_b = _new_pin(na, bit_nodes, cell["connections"]["B"][0], 0, rx=ib_x, ry=ib_y)
        out_y = _new_pin(na, bit_nodes, cell["connections"]["Y"][0], 1, rx=ox, ry=oy)
        comp = _make_comp(cv_type, x_cell, y_cell,
          ["RIGHT", n_inp, 1],
          {"inp": [n for n in [inp_a, inp_b] if n is not None], "output1": out_y})
        components.setdefault(cv_type, []).append(comp)
        y_cell += component_height(cv_type, inputLength=2) + pin_clearance(2)
      elif ctype == "$_NOT_":
        inp_a = _new_pin(na, bit_nodes, cell["connections"]["A"][0], 0, rx=-10, ry=0)
        out_y = _new_pin(na, bit_nodes, cell["connections"]["Y"][0], 1, rx=20, ry=0)
        comp = _make_comp("NotGate", x_cell, y_cell,
          ["RIGHT", 1], {"inp1": inp_a, "output1": out_y})
        components.setdefault("NotGate", []).append(comp)
        y_cell += component_height("NotGate") + pin_clearance(1)
      elif ctype.startswith(_YOSYS_DFF_PREFIX):
        conns = cell["connections"]
        dx, dy = pin_pos("DflipFlop", "dInp")
        cx, cy = pin_pos("DflipFlop", "clockInp")
        qx, qy = pin_pos("DflipFlop", "qOutput")
        qix, qiy = pin_pos("DflipFlop", "qInvOutput")
        rx_, ry_ = pin_pos("DflipFlop", "reset")
        px, py = pin_pos("DflipFlop", "preset")
        ex, ey = pin_pos("DflipFlop", "en")
        d_node = _new_pin(na, bit_nodes, conns["D"][0], 0, rx=dx, ry=dy)
        clk_node = _new_pin(na, bit_nodes, conns["C"][0], 0, rx=cx, ry=cy)
        q_node = _new_pin(na, bit_nodes, conns["Q"][0], 1, rx=qx, ry=qy)
        q_inv = na.alloc(qix, qiy, 1, 1)
        rst = _new_pin(na, bit_nodes, conns["R"][0], 0, rx=rx_, ry=ry_) if "R" in conns else na.alloc(rx_, ry_, 0, 1)
        preset = _new_pin(na, bit_nodes, conns["S"][0], 0, rx=px, ry=py) if "S" in conns else na.alloc(px, py, 0, 1)
        en = _new_pin(na, bit_nodes, conns["E"][0], 0, rx=ex, ry=ey) if "E" in conns else na.alloc(ex, ey, 0, 1)
        comp = _make_comp("DflipFlop", x_cell, y_cell,
          ["RIGHT", 1],
          {"clockInp": clk_node, "dInp": d_node, "qOutput": q_node,
           "qInvOutput": q_inv, "reset": rst, "preset": preset, "en": en})
        components.setdefault("DflipFlop", []).append(comp)
        y_cell += component_height("DflipFlop") + pin_clearance(2)
      elif ctype == "$_MUX_":
        _css = 1
        ia_x, ia_y = pin_pos("Multiplexer", "inp", index=0, controlSignalSize=_css)
        ib_x, ib_y = pin_pos("Multiplexer", "inp", index=1, controlSignalSize=_css)
        sx, sy = pin_pos("Multiplexer", "controlSignalInput", controlSignalSize=_css)
        ox, oy = pin_pos("Multiplexer", "output1", controlSignalSize=_css)
        inp_a = _new_pin(na, bit_nodes, cell["connections"]["A"][0], 0, rx=ia_x, ry=ia_y)
        inp_b = _new_pin(na, bit_nodes, cell["connections"]["B"][0], 0, rx=ib_x, ry=ib_y)
        sel = _new_pin(na, bit_nodes, cell["connections"]["S"][0], 0, rx=sx, ry=sy)
        out_y = _new_pin(na, bit_nodes, cell["connections"]["Y"][0], 1, rx=ox, ry=oy)
        comp = _make_comp("Multiplexer", x_cell, y_cell,
          ["RIGHT", 1, 1],
          {"inp": [n for n in [inp_a, inp_b] if n is not None],
           "output1": out_y, "controlSignalInput": sel},
          propagation_delay=10)
        components.setdefault("Multiplexer", []).append(comp)
        y_cell += component_height("Multiplexer", controlSignalSize=1) + pin_clearance(2)
      else:
        _log.warning("unmapped cell type '%s' (%s)", ctype, cell_name)
        continue
      y_cell += GATE_V_CELL_PAD

  return components, cell_positions, cv_subcircuits, sc_comps
