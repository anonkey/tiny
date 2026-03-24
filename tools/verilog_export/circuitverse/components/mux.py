"""High-level multiplexer: $mux."""

from circuitverse.components._common import pin_clearance, _new_bus_pin, _param_int
from circuitverse.components.registry import component_height


def place_mux(cell, conns, na, bit_nodes, components, x, y):
  """Place a multi-bit mux. Returns y-advance."""
  bw = _param_int(cell, "WIDTH", len(conns["Y"]))
  inp_a = _new_bus_pin(na, bit_nodes, conns["A"], 0, bw, rx=-10, ry=-10)
  inp_b = _new_bus_pin(na, bit_nodes, conns["B"], 0, bw, rx=-10, ry=10)
  sel = _new_bus_pin(na, bit_nodes, conns["S"], 0, 1, rx=0, ry=20)
  out_y = _new_bus_pin(na, bit_nodes, conns["Y"], 1, bw, rx=10, ry=0)
  comp = {
    "x": x, "y": y,
    "objectType": "Multiplexer",
    "label": "",
    "direction": "RIGHT",
    "labelDirection": "LEFT",
    "propagationDelay": 10,
    "customData": {
      "constructorParamaters": ["RIGHT", bw, 1],
      "nodes": {
        "inp": [inp_a, inp_b],
        "output1": out_y,
        "controlSignalInput": sel,
      },
    },
  }
  components.setdefault("Multiplexer", []).append(comp)
  return component_height("Multiplexer", controlSignalSize=1) + pin_clearance(2)
