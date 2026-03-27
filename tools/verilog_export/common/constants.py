"""Shared constants and pin helpers for component handlers."""

from common.node_alloc import _CVNodeAlloc
from common.emit import (
  CTOR_PARAMS_KEY, _make_comp, _append_comp,
  emit_constant, emit_not_gate, emit_zero_extend,
  register_bits, emit_splitter, emit_split_reduce,
)

# ── Gate-level mapping ────────────────────────────────────────────────────

_YOSYS_GATE_TO_CV = {
  "$_AND_":  ("AndGate",  2),
  "$_OR_":   ("OrGate",   2),
  "$_NOT_":  ("NotGate",  1),
  "$_NAND_": ("NandGate", 2),
  "$_NOR_":  ("NorGate",  2),
  "$_XOR_":  ("XorGate",  2),
  "$_XNOR_": ("XnorGate", 2),
  "$_MUX_":  ("Multiplexer", None),
}

_YOSYS_DFF_PREFIX = "$_DFF"

# ── Layout constants ─────────────────────────────────────────────────────
# All values are multiples of 10 (CircuitVerse grid = 10x10).

GRID_UNIT = 10       # CircuitVerse snap grid (all coords are multiples of this)
V_CELL_PAD = 20      # extra vertical gap between components in a column
H_COL_PAD = 20       # extra horizontal padding between adjacent columns
CELL_GAP = 300   # vertical gap between components in the same column
COL_GAP = 300    # horizontal gap between columns (room for routing)
X_START = 400    # x of first gate column (leaves room for input + splitter)

# Gate-level overrides — wider channels for dense 1-bit netlists
GATE_COL_GAP = 450       # 1.5x wider horizontal routing channels
GATE_V_CELL_PAD = 60     # 3x more vertical gap between gates


def pin_clearance(n):
  """Clearance for n pins on one side: 20 if n<=1, else (n+1)*10."""
  return 20 if n <= 1 else (n + 1) * 10


# ── Pin helpers ──────────────────────────────────────────────────────────

def _new_pin(na, bit_nodes, bit_idx, ntype=2, bit_width=1, rx=0, ry=0):
  """Allocate a fresh node for a pin and register it on its net."""
  if isinstance(bit_idx, str):
    return None
  nid = na.alloc(rx, ry, ntype, bit_width)
  bit_nodes.setdefault(bit_idx, []).append(nid)
  return nid


def _new_bus_pin(na, bit_nodes, bits, ntype, bw, rx=0, ry=0):
  """Allocate a single multi-bit node and register all its bit indices."""
  nid = na.alloc(rx, ry, ntype, bw)
  register_bits(na, bit_nodes, bits, nid, bw)
  return nid


# ── Parameter extraction ─────────────────────────────────────────────────

def _param_int(cell, name, default=1):
  """Get an integer parameter from a Yosys cell."""
  val = cell.get("parameters", {}).get(name, default)
  if isinstance(val, str):
    return int(val, 2) if all(c in "01" for c in val) else int(val)
  return int(val)


def _param_bits(cell, name):
  """Get a parameter as a binary string (MSB first)."""
  val = cell.get("parameters", {}).get(name, "0")
  if isinstance(val, int):
    return bin(val)[2:]
  return val


# ── Width adaptation ─────────────────────────────────────────────────────

def _adapt_single(na, bit_nodes, components, bits, port_bw, target_bw,
                   x, y, rx=0, ry=0):
  """Zero-extend a single port to target_bw. Returns (node, extra_h)."""
  if port_bw == target_bw:
    return _new_bus_pin(na, bit_nodes, bits, 0, port_bw, rx=rx, ry=ry), 0
  ext_comps, narrow, wide = emit_zero_extend(
    na, bit_nodes, port_bw, target_bw, x - 80, y)
  register_bits(na, bit_nodes, bits, narrow, port_bw)
  for c in ext_comps:
    components.setdefault(c["objectType"], []).append(c)
  return wide, 40


def _adapt_width(na, bit_nodes, components, cell, target_bw, x, y,
                  a_rx=-20, a_ry=-10, b_rx=-20, b_ry=10):
  """Create zero-extended inputs A and B matched to target_bw.

  Returns (a_node, b_node, extra_components_height).
  """
  conns = cell["connections"]
  a_bw = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  a_node, eh_a = _adapt_single(na, bit_nodes, components,
    conns["A"], a_bw, target_bw, x, y, rx=a_rx, ry=a_ry)
  b_node, eh_b = _adapt_single(na, bit_nodes, components,
    conns["B"], b_bw, target_bw, x, y + 40, rx=b_rx, ry=b_ry)
  return a_node, b_node, eh_a + eh_b


# ── Polarity-conditional NOT insertion ───────────────────────────────────

def _maybe_invert(na, bit_nodes, components, raw_node, target_node,
                  polarity, x, y):
  """Insert NOT gate if polarity==0, else connect raw_node to target_node."""
  if polarity == 0:
    not_comp, not_inp, not_out = emit_not_gate(na, bit_nodes, 1, x, y)
    na.connect(raw_node, not_inp)
    components.setdefault("NotGate", []).append(not_comp)
    na.connect(not_out, target_node)
  else:
    na.connect(raw_node, target_node)
