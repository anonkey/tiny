"""High-level multiplexer / demultiplexer: $mux."""

from __future__ import annotations


from common.constants import pin_clearance, _new_bus_pin, _param_int, _append_comp
from common.node_alloc import _CVNodeAlloc
from common.types import BitNodes, CompMap, YosysCell, YosysConns
from synthesis.gates.registry import component_height


def _is_demux_pattern(conns: YosysConns) -> bool:
  """Detect if a $mux cell is acting as a demultiplexer.

  A demux uses a $mux to route a narrow input into one half of a wider
  output bus, padding the other half with constant zeros.  Both A and B
  contain constant padding bits in complementary positions.
  """
  a_has_const = any(isinstance(b, str) for b in conns["A"])
  b_has_const = any(isinstance(b, str) for b in conns["B"])
  return a_has_const and b_has_const


def place_demux(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc,
                bit_nodes: BitNodes, components: CompMap,
                x: int, y: int) -> int:
  """Place a demultiplexer derived from a $mux with constant padding."""
  width = _param_int(cell, "WIDTH", len(conns["Y"]))
  half = width // 2
  # Data input — the real (non-padding) bits common to A and B
  real_bits = [b for b in conns["A"] if not isinstance(b, str)]
  data_bw = len(real_bits)
  data_in = _new_bus_pin(na, bit_nodes, real_bits, 0, data_bw, rx=10, ry=0)
  # Control
  sel = _new_bus_pin(na, bit_nodes, conns["S"], 0, 1, rx=0, ry=20)
  # Outputs — split Y into lower and upper halves
  out_lo = _new_bus_pin(na, bit_nodes, conns["Y"][:half], 1, half, rx=-10, ry=-10)
  out_hi = _new_bus_pin(na, bit_nodes, conns["Y"][half:], 1, half, rx=-10, ry=10)
  _append_comp(components, "Demultiplexer", x, y,
    ["LEFT", data_bw, 1],
    {"input": data_in, "output1": [out_lo, out_hi], "controlSignalInput": sel},
    propagation_delay=10, direction="LEFT")
  return component_height("Demultiplexer", controlSignalSize=1) + pin_clearance(2)


def place_mux(cell: YosysCell, conns: YosysConns, na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap, x: int, y: int) -> int:
  """Place a multi-bit mux (or demux if padding detected). Returns y-advance."""
  if _is_demux_pattern(conns):
    return place_demux(cell, conns, na, bit_nodes, components, x, y)
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
