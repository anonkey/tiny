"""High-level DFF variants: $dff, $dffe, $adff, $adffe, $sdff, $sdffe."""

from circuitverse.components._common import (
  pin_clearance, _new_bus_pin, _param_int, _maybe_invert,
)
from cv_emit import emit_constant, register_bits
from circuitverse.components.registry import pin_pos, component_height


def place_dff(cell_name, cell, conns, na, bit_nodes, components, x, y):
  """Place a high-level DFF variant. Returns y-advance."""
  bw = _param_int(cell, "WIDTH", len(conns.get("D", [])))
  clk_pol = _param_int(cell, "CLK_POLARITY", 1)

  dx, dy = pin_pos("DflipFlop", "dInp")
  cx, cy = pin_pos("DflipFlop", "clockInp")
  qx, qy = pin_pos("DflipFlop", "qOutput")
  qix, qiy = pin_pos("DflipFlop", "qInvOutput")
  rx_, ry_ = pin_pos("DflipFlop", "reset")
  px, py = pin_pos("DflipFlop", "preset")
  ex, ey = pin_pos("DflipFlop", "en")

  # D input
  d_node = _new_bus_pin(na, bit_nodes, conns["D"], 0, bw, rx=dx, ry=dy)

  # Clock — possibly inverted
  clk_raw = _new_bus_pin(na, bit_nodes, conns["CLK"], 0, 1, rx=cx, ry=cy)
  clk_node = na.alloc(cx, cy, 0, 1)
  _maybe_invert(na, bit_nodes, components, clk_raw, clk_node,
                clk_pol, x - 60, y + 10)

  # Q output
  q_node = _new_bus_pin(na, bit_nodes, conns["Q"], 1, bw, rx=qx, ry=qy)
  q_inv = na.alloc(qix, qiy, 1, bw)

  # Reset
  rst_node = na.alloc(rx_, ry_, 0, 1)
  if "ARST" in conns:
    arst_pol = _param_int(cell, "ARST_POLARITY", 1)
    arst_raw = _new_bus_pin(na, bit_nodes, conns["ARST"], 0, 1, rx=rx_, ry=ry_)
    _maybe_invert(na, bit_nodes, components, arst_raw, rst_node,
                  arst_pol, x - 60, y + 20)
  elif "SRST" in conns:
    srst_pol = _param_int(cell, "SRST_POLARITY", 1)
    srst_raw = _new_bus_pin(na, bit_nodes, conns["SRST"], 0, 1, rx=rx_, ry=ry_)
    _maybe_invert(na, bit_nodes, components, srst_raw, rst_node,
                  srst_pol, x - 60, y + 20)

  # Preset (from ARST_VALUE)
  preset_node = na.alloc(px, py, 0, bw)
  arst_val = cell.get("parameters", {}).get("ARST_VALUE")
  if arst_val is not None:
    if isinstance(arst_val, int):
      val_str = format(arst_val, f"0{bw}b")
    else:
      val_str = str(arst_val).zfill(bw)
    pval_comp, pval_out = emit_constant(
      na, bit_nodes, val_str, bw, x - 60, y + 30)
    components.setdefault("ConstantVal", []).append(pval_comp)
    na.connect(pval_out, preset_node)

  # Enable
  en_node = na.alloc(ex, ey, 0, 1)
  if "EN" in conns:
    en_pol = _param_int(cell, "EN_POLARITY", 1)
    en_raw = _new_bus_pin(na, bit_nodes, conns["EN"], 0, 1, rx=ex, ry=ey)
    _maybe_invert(na, bit_nodes, components, en_raw, en_node,
                  en_pol, x - 60, y + 30)

  comp = {
    "x": x, "y": y,
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
        "reset": rst_node,
        "preset": preset_node,
        "en": en_node,
      },
      "constructorParamaters": ["RIGHT", bw],
    },
  }
  components.setdefault("DflipFlop", []).append(comp)
  return component_height("DflipFlop") + pin_clearance(2)
