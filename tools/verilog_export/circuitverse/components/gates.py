"""Gate-level (1-bit) cell placement: $_AND_, $_OR_, $_NOT_, $_MUX_, $_DFF*."""

import sys

from circuitverse.components._common import (
  _YOSYS_GATE_TO_CV, _YOSYS_DFF_PREFIX, CELL_GAP, CELL_MARGIN, COL_GAP, X_START,
  _new_pin,
)
from circuitverse.components.registry import pin_pos, gate_output_pos, component_height


def place_gate_cells(col_cells, na, bit_nodes):
  """Place gate-level (1-bit) cells. Returns components dict."""
  from circuitverse.yosys_layout import _count_crossing_nets
  components = {}

  max_crossing = _count_crossing_nets(col_cells)
  dynamic_extra = max(0, max_crossing * 30)

  for depth in sorted(col_cells.keys()):
    x_cell = X_START + depth * COL_GAP
    y_cell = 0

    for cell_name, cell in col_cells[depth]:
      ctype = cell["type"]
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
        comp = {
          "x": x_cell, "y": y_cell,
          "objectType": cv_type,
          "label": "",
          "direction": "RIGHT",
          "labelDirection": "LEFT",
          "propagationDelay": 100,
          "customData": {
            "constructorParamaters": ["RIGHT", n_inp, 1],
            "nodes": {
              "inp": [n for n in [inp_a, inp_b] if n is not None],
              "output1": out_y,
            },
          },
        }
        components.setdefault(cv_type, []).append(comp)
        y_cell += component_height(cv_type, inputLength=2) + CELL_MARGIN + dynamic_extra

      elif ctype == "$_NOT_":
        inp_a = _new_pin(na, bit_nodes, cell["connections"]["A"][0], 0, rx=-10, ry=0)
        out_y = _new_pin(na, bit_nodes, cell["connections"]["Y"][0], 1, rx=20, ry=0)
        comp = {
          "x": x_cell, "y": y_cell,
          "objectType": "NotGate",
          "label": "",
          "direction": "RIGHT",
          "labelDirection": "LEFT",
          "propagationDelay": 100,
          "customData": {
            "constructorParamaters": ["RIGHT", 1],
            "nodes": {"inp1": inp_a, "output1": out_y},
          },
        }
        components.setdefault("NotGate", []).append(comp)
        y_cell += component_height("NotGate") + CELL_MARGIN + dynamic_extra

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
        comp = {
          "x": x_cell, "y": y_cell,
          "objectType": "DflipFlop",
          "label": "",
          "direction": "RIGHT",
          "labelDirection": "LEFT",
          "propagationDelay": 100,
          "customData": {
            "nodes": {
              "clockInp": clk_node,
              "dInp": d_node,
              "qOutput": q_node,
              "qInvOutput": q_inv,
              "reset": rst,
              "preset": preset,
              "en": en,
            },
            "constructorParamaters": ["RIGHT", 1],
          },
        }
        components.setdefault("DflipFlop", []).append(comp)
        y_cell += component_height("DflipFlop") + CELL_MARGIN + dynamic_extra

      elif ctype == "$_MUX_":
        inp_a = _new_pin(na, bit_nodes, cell["connections"]["A"][0], 0, rx=-10, ry=-10)
        inp_b = _new_pin(na, bit_nodes, cell["connections"]["B"][0], 0, rx=-10, ry=10)
        sel = _new_pin(na, bit_nodes, cell["connections"]["S"][0], 0, rx=0, ry=20)
        out_y = _new_pin(na, bit_nodes, cell["connections"]["Y"][0], 1, rx=10, ry=0)
        comp = {
          "x": x_cell, "y": y_cell,
          "objectType": "Multiplexer",
          "label": "",
          "direction": "RIGHT",
          "labelDirection": "LEFT",
          "propagationDelay": 10,
          "customData": {
            "constructorParamaters": ["RIGHT", 1, 1],
            "nodes": {
              "inp": [n for n in [inp_a, inp_b] if n is not None],
              "output1": out_y,
              "controlSignalInput": sel,
            },
          },
        }
        components.setdefault("Multiplexer", []).append(comp)
        y_cell += component_height("Multiplexer", controlSignalSize=1) + CELL_MARGIN + dynamic_extra

      else:
        print(f"  warning: unmapped cell type '{ctype}' ({cell_name})",
              file=sys.stderr)

  return components
