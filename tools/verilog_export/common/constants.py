"""Shared constants and pin helpers for component handlers."""

from __future__ import annotations

from typing import Any

from common.node_alloc import _CVNodeAlloc
from common.types import BitNodes, CompDict, CompMap
from common.emit import (
  CTOR_PARAMS_KEY, _make_comp, _append_comp,
  emit_constant, emit_not_gate, emit_zero_extend,
  register_bits, emit_splitter, emit_split_reduce,
)

# ── Gate-level mapping ────────────────────────────────────────────────────

_YOSYS_GATE_TO_CV: dict[str, tuple[str, int | None]] = {
  "$_AND_":  ("AndGate",  2),
  "$_OR_":   ("OrGate",   2),
  "$_NOT_":  ("NotGate",  1),
  "$_NAND_": ("NandGate", 2),
  "$_NOR_":  ("NorGate",  2),
  "$_XOR_":  ("XorGate",  2),
  "$_XNOR_": ("XnorGate", 2),
  "$_MUX_":  ("Multiplexer", None),
}

_YOSYS_DFF_PREFIX: str = "$_DFF"

# ── Layout constants ─────────────────────────────────────────────────────
# All values are multiples of 10 (CircuitVerse grid = 10x10).

GRID_UNIT: int = 10       # CircuitVerse snap grid (all coords are multiples of this)
V_CELL_PAD: int = 20      # extra vertical gap between components in a column
H_COL_PAD: int = 20       # extra horizontal padding between adjacent columns
CELL_GAP: int = 300   # vertical gap between components in the same column
COL_GAP: int = 300    # horizontal gap between columns (room for routing)
X_START: int = 400    # x of first gate column (leaves room for input + splitter)

# Gate-level overrides — wider channels for dense 1-bit netlists
GATE_COL_GAP: int = 450       # 1.5x wider horizontal routing channels
GATE_V_CELL_PAD: int = 60     # 3x more vertical gap between gates


def pin_clearance(n: int) -> int:
  """Clearance for n pins on one side: 20 if n<=1, else (n+1)*10."""
  return 20 if n <= 1 else (n + 1) * 10


# ── Pin helpers ──────────────────────────────────────────────────────────

def _new_pin(na: _CVNodeAlloc, bit_nodes: BitNodes, bit_idx: int | str,
             ntype: int = 2, bit_width: int = 1,
             rx: int = 0, ry: int = 0) -> int | None:
  """Allocate a fresh node for a pin and register it on its net."""
  if isinstance(bit_idx, str):
    return None
  nid: int = na.alloc(rx, ry, ntype, bit_width)
  bit_nodes.setdefault(bit_idx, []).append(nid)
  return nid


def _new_bus_pin(na: _CVNodeAlloc, bit_nodes: BitNodes,
                 bits: list[int | str], ntype: int, bw: int,
                 rx: int = 0, ry: int = 0) -> int:
  """Allocate a single multi-bit node and register all its bit indices."""
  nid: int = na.alloc(rx, ry, ntype, bw)
  register_bits(na, bit_nodes, bits, nid, bw)
  return nid


# ── Parameter extraction ─────────────────────────────────────────────────

def _param_int(cell: dict[str, Any], name: str, default: int = 1) -> int:
  """Get an integer parameter from a Yosys cell."""
  val: Any = cell.get("parameters", {}).get(name, default)
  if isinstance(val, str):
    return int(val, 2) if all(c in "01" for c in val) else int(val)
  return int(val)


def _param_bits(cell: dict[str, Any], name: str) -> str:
  """Get a parameter as a binary string (MSB first)."""
  val: Any = cell.get("parameters", {}).get(name, "0")
  if isinstance(val, int):
    return bin(val)[2:]
  return val


# ── Width adaptation ─────────────────────────────────────────────────────

def _adapt_single(na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap,
                   bits: list[int | str], port_bw: int, target_bw: int,
                   x: int, y: int, rx: int = 0,
                   ry: int = 0) -> tuple[int, int]:
  """Zero-extend a single port to target_bw. Returns (node, extra_h)."""
  if port_bw == target_bw:
    return _new_bus_pin(na, bit_nodes, bits, 0, port_bw, rx=rx, ry=ry), 0
  ext_comps: list[CompDict]
  narrow: int
  wide: int
  ext_comps, narrow, wide = emit_zero_extend(
    na, bit_nodes, port_bw, target_bw, x - 80, y)
  register_bits(na, bit_nodes, bits, narrow, port_bw)
  for c in ext_comps:
    components.setdefault(c["objectType"], []).append(c)
  return wide, 40


def _adapt_width(na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap,
                  cell: dict[str, Any], target_bw: int, x: int, y: int,
                  a_rx: int = -20, a_ry: int = -10,
                  b_rx: int = -20, b_ry: int = 10) -> tuple[int, int, int]:
  """Create zero-extended inputs A and B matched to target_bw.

  Returns (a_node, b_node, extra_components_height).
  """
  conns: dict[str, list[int | str]] = cell["connections"]
  a_bw: int = _param_int(cell, "A_WIDTH", len(conns.get("A", [])))
  b_bw: int = _param_int(cell, "B_WIDTH", len(conns.get("B", [])))
  a_node: int
  eh_a: int
  a_node, eh_a = _adapt_single(na, bit_nodes, components,
    conns["A"], a_bw, target_bw, x, y, rx=a_rx, ry=a_ry)
  b_node: int
  eh_b: int
  b_node, eh_b = _adapt_single(na, bit_nodes, components,
    conns["B"], b_bw, target_bw, x, y + 40, rx=b_rx, ry=b_ry)
  return a_node, b_node, eh_a + eh_b


# ── Polarity-conditional NOT insertion ───────────────────────────────────

def _maybe_invert(na: _CVNodeAlloc, bit_nodes: BitNodes, components: CompMap,
                  raw_node: int, target_node: int,
                  polarity: int, x: int, y: int) -> None:
  """Insert NOT gate if polarity==0, else connect raw_node to target_node."""
  if polarity == 0:
    not_comp: CompDict
    not_inp: int
    not_out: int
    not_comp, not_inp, not_out = emit_not_gate(na, bit_nodes, 1, x, y)
    na.connect(raw_node, not_inp)
    components.setdefault("NotGate", []).append(not_comp)
    na.connect(not_out, target_node)
  else:
    na.connect(raw_node, target_node)
