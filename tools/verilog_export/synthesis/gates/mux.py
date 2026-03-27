"""High-level multiplexer: $mux."""

from __future__ import annotations

from typing import Any

from common.constants import pin_clearance, _new_bus_pin, _param_int, _append_comp
from common.node_alloc import _CVNodeAlloc
from common.types import BitNodes, CompMap
from synthesis.gates.registry import component_height


def place_mux(cell: dict[str, Any], conns: dict[str, Any], na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a multi-bit mux. Returns y-advance."""
  bw = _param_int(cell, "WIDTH", len(conns["Y"]))
  inp_a = _new_bus_pin(na, bit_nodes, conns["A"], 0, bw, rx=-10, ry=-10)
  inp_b = _new_bus_pin(na, bit_nodes, conns["B"], 0, bw, rx=-10, ry=10)
  sel = _new_bus_pin(na, bit_nodes, conns["S"], 0, 1, rx=0, ry=20)
  out_y = _new_bus_pin(na, bit_nodes, conns["Y"], 1, bw, rx=10, ry=0)
  _append_comp(components, "Multiplexer", x, y,
    ["RIGHT", bw, 1],
    {"inp": [inp_a, inp_b], "output1": out_y, "controlSignalInput": sel},
    propagation_delay=10)
  return component_height("Multiplexer", controlSignalSize=1) + pin_clearance(2)
