"""Layout helpers for CircuitVerse: topo sort, port/cell placement.

Supports both gate-level (1-bit $_AND_ etc.) and high-level ($add etc.) cells.
Cell handlers live in components/ — this module provides topo sort and dispatch.
"""

import logging
from collections import namedtuple

_log = logging.getLogger(__name__)

from circuitverse.components._common import (
  _YOSYS_DFF_PREFIX, COL_GAP, X_START, H_COL_PAD, V_CELL_PAD, GRID_UNIT,
  pin_clearance, _new_pin, _new_bus_pin, _param_int, _param_bits,
  _adapt_width, _maybe_invert,
)
from circuitverse.components import (
  place_gate_cells,
  place_logic, place_mux,
  place_add, place_sub, place_mul, place_divmod, place_neg,
  place_shift,
  place_eq_ne, place_lt_gt_le_ge,
  place_reduce, place_logic_not, place_logic_and_or,
  place_dff,
  place_slice, place_concat,
  place_mem_v2,
)


# ── Unified cell registry ─────────────────────────────────────────────────
# Single source of truth for handler, extent, and pin info per Yosys cell type.
# handler:     place_* function (None for gate-level types dispatched separately)
# cv_type:     CircuitVerse component type (for dimension lookup)
# extra_left:  sub-component offset added to left extent
# extra_right: sub-component offset added to right extent
# left_pins:   outward-facing pins on left (None → compute dynamically)
# right_pins:  outward-facing pins on right (None → compute dynamically)

CellInfo = namedtuple("CellInfo", [
  "handler", "cv_type", "extra_left", "extra_right", "left_pins", "right_pins",
])

_CELL_REGISTRY = {
  # ── Logic gates (high-level) ──
  "$and":         CellInfo(place_logic,      "AndGate",       0,   0,   2, 1),
  "$or":          CellInfo(place_logic,      "OrGate",        0,   0,   2, 1),
  "$xor":         CellInfo(place_logic,      "XorGate",       0,   0,   2, 1),
  "$xnor":        CellInfo(place_logic,      "XnorGate",      0,   0,   2, 1),
  "$not":         CellInfo(place_logic,      "NotGate",       0,   0,   1, 1),
  "$mux":         CellInfo(place_mux,        "Multiplexer",   0,   0,   2, 1),
  # ── Arithmetic ──
  "$add":         CellInfo(place_add,        "Adder",         0,   80,  3, 2),   # splitter at x+60
  "$sub":         CellInfo(place_sub,        "ALU",           80,  0,   0, 1),   # ConstantVal at x-60
  "$mul":         CellInfo(place_mul,        "verilogMultiplier", 0, 0, 2, 1),
  "$div":         CellInfo(place_divmod,     "verilogDivider", 0,  0,   2, 2),   # quotient+remainder
  "$mod":         CellInfo(place_divmod,     "verilogDivider", 0,  0,   2, 2),
  "$neg":         CellInfo(place_neg,        "TwoComplement", 0,   0,   1, 1),
  # ── Shifts ──
  "$shl":         CellInfo(place_shift,      "verilogShiftLeft",  0, 0, 2, 1),
  "$sshl":        CellInfo(place_shift,      "verilogShiftLeft",  0, 0, 2, 1),
  "$shr":         CellInfo(place_shift,      "verilogShiftRight", 0, 0, 2, 1),
  "$sshr":        CellInfo(place_shift,      "verilogShiftRight", 0, 0, 2, 1),
  # ── Comparisons ──
  "$eq":          CellInfo(place_eq_ne,      "XnorGate",      0,   140, 2, 1),   # split_reduce chain
  "$ne":          CellInfo(place_eq_ne,      "XnorGate",      0,   140, 2, 1),
  "$lt":          CellInfo(place_lt_gt_le_ge,"ALU",           80,  140, 0, 1),   # ConstantVal + splitter + NotGate
  "$gt":          CellInfo(place_lt_gt_le_ge,"ALU",           80,  140, 0, 1),
  "$le":          CellInfo(place_lt_gt_le_ge,"ALU",           80,  140, 0, 1),
  "$ge":          CellInfo(place_lt_gt_le_ge,"ALU",           80,  140, 0, 1),
  # ── Reductions ──
  "$logic_not":   CellInfo(place_logic_not,  "NorGate",       80,  40,  1, 1),   # split_reduce at x-60/x+20
  "$logic_and":   CellInfo(place_logic_and_or,"AndGate",      100, 60,  1, 1),   # sub-comps at x-80
  "$logic_or":    CellInfo(place_logic_and_or,"OrGate",       100, 60,  1, 1),
  "$reduce_and":  CellInfo(place_reduce,     "AndGate",       60,  60,  1, 1),   # split_reduce: spl x-40, gate x+40
  "$reduce_or":   CellInfo(place_reduce,     "OrGate",        60,  60,  1, 1),
  "$reduce_xor":  CellInfo(place_reduce,     "XorGate",       60,  60,  1, 1),
  "$reduce_xnor": CellInfo(place_reduce,     "XnorGate",      60,  60,  1, 1),
  "$reduce_bool": CellInfo(place_reduce,     "OrGate",        60,  60,  1, 1),
  # ── DFFs ──
  "$dff":         CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2),   # ConstantVal/NotGate at x-60
  "$dffe":        CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2),
  "$adff":        CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2),
  "$adffe":       CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2),
  "$sdff":        CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2),
  "$sdffe":       CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2),
  # ── Bus ops ──
  "$slice":       CellInfo(place_slice,      "Splitter",      0,   0,   1, None),  # right_pins computed dynamically
  "$concat":      CellInfo(place_concat,     "Splitter",      0,   0,   2, 1),
  "$mem_v2":      CellInfo(place_mem_v2,     "verilogRAM",    0,   0,   4, 1),    # approximate
  # ── Gate-level types (no handler — dispatched via place_gate_cells) ──
  "$_AND_":       CellInfo(None, "AndGate",      0, 0, 2, 1),
  "$_OR_":        CellInfo(None, "OrGate",       0, 0, 2, 1),
  "$_NOT_":       CellInfo(None, "NotGate",      0, 0, 1, 1),
  "$_NAND_":      CellInfo(None, "NandGate",     0, 0, 2, 1),
  "$_NOR_":       CellInfo(None, "NorGate",      0, 0, 2, 1),
  "$_XOR_":       CellInfo(None, "XorGate",      0, 0, 2, 1),
  "$_XNOR_":      CellInfo(None, "XnorGate",     0, 0, 2, 1),
  "$_MUX_":       CellInfo(None, "Multiplexer",  0, 0, 2, 1),  # select is bottom
}


# ── Topological sort ───────────────────────────────────────────────────────

def topo_sort_cells(ymod):
  """Extract cells, compute depth, return (sorted_cells, col_cells).

  Uses port_directions from Yosys JSON to automatically determine
  input/output ports for any cell type.
  """
  cells = [(n, c) for n, c in ymod.get("cells", {}).items()
           if c["type"] != "$scopeinfo"]

  bit_producer = {}
  for cell_name, cell in cells:
    dirs = cell.get("port_directions", {})
    for pn, d in dirs.items():
      if d == "output":
        for b in cell["connections"].get(pn, []):
          if not isinstance(b, str):
            bit_producer[b] = cell_name

  cell_depth = {}
  cell_by_name = {n: c for n, c in cells}

  def _depth(cname, visiting=None):
    if cname in cell_depth:
      return cell_depth[cname]
    if visiting is None:
      visiting = set()
    if cname in visiting:
      return 0
    visiting.add(cname)
    cell = cell_by_name[cname]
    dirs = cell.get("port_directions", {})
    ctype = cell["type"]
    if ctype.startswith("$dff") or ctype.startswith("$adff") or ctype.startswith("$sdff"):
      data_ports = ["D"]
    elif ctype.startswith(_YOSYS_DFF_PREFIX):
      data_ports = ["D"]
    else:
      data_ports = [pn for pn, d in dirs.items() if d == "input"]

    max_d = 0
    for pn in data_ports:
      for b in cell["connections"].get(pn, []):
        if not isinstance(b, str) and b in bit_producer:
          prod = bit_producer[b]
          if prod != cname:
            max_d = max(max_d, _depth(prod, visiting) + 1)
    cell_depth[cname] = max_d
    return max_d

  for cname, _ in cells:
    _depth(cname)

  sorted_cells = sorted(cells, key=lambda nc: (cell_depth[nc[0]],
                                                 cells.index(nc)))
  col_cells = {}
  for cname, cell in sorted_cells:
    d = cell_depth[cname]
    col_cells.setdefault(d, []).append((cname, cell))

  return sorted_cells, col_cells


# ── Horizontal extent per Yosys cell type ────────────────────────────────

def _cell_h_extent(ctype, cell):
  """Return (left, right) reach from column center for a Yosys cell."""
  from circuitverse.components.registry import dimensions
  # Gate-level DFF types (prefix match, not in registry)
  if ctype.startswith("$_DFF"):
    return (20, 20)
  info = _CELL_REGISTRY.get(ctype)
  if not info:
    _log.debug("_cell_h_extent: unknown cell type '%s', using fallback (40, 40)", ctype)
    return (40, 40)  # fallback
  cv_type = info.cv_type
  try:
    params = {}
    if cv_type in ("AndGate", "OrGate", "NandGate", "NorGate", "XorGate", "XnorGate"):
      params["inputLength"] = 2
    dim = dimensions(cv_type, **params)
    left = dim["left"] + info.extra_left
    right = dim["right"] + info.extra_right
  except KeyError:
    _log.debug("_cell_h_extent: dimensions lookup failed for '%s', using base (20, 20)", cv_type)
    left = 20 + info.extra_left
    right = 20 + info.extra_right
  return (left, right)


def _cell_outward_pins(ctype, cell):
  """Return (left_pins, right_pins) outward-facing horizontal pin counts.

  'Outward' means: leftmost sub-component's left side pin count,
  rightmost sub-component's right side pin count.
  """
  # Gate-level DFF types (prefix match, not in registry)
  if ctype.startswith("$_DFF"):
    return (2, 2)
  info = _CELL_REGISTRY.get(ctype)
  if not info:
    _log.debug("_cell_outward_pins: unknown cell type '%s', using fallback (1, 1)", ctype)
    return (1, 1)  # fallback
  lp = info.left_pins
  rp = info.right_pins
  # Dynamic pin computation (right_pins=None for $slice)
  if rp is None:
    a_bw = _param_int(cell, "A_WIDTH", 1) if cell else 1
    y_bw = _param_int(cell, "Y_WIDTH", 1) if cell else 1
    offset = _param_int(cell, "OFFSET", 0) if cell else 0
    groups = 1  # Y output
    if offset > 0:
      groups += 1
    if a_bw - offset - y_bw > 0:
      groups += 1
    rp = groups
  return (lp, rp)


def _col_extents(col_cells):
  """Compute max (left, right) extent and outward pin counts per column."""
  extents = {}
  for depth, cells in col_cells.items():
    max_left = 0
    max_right = 0
    max_left_pins = 0
    max_right_pins = 0
    for _, cell in cells:
      l, r = _cell_h_extent(cell["type"], cell)
      lp, rp = _cell_outward_pins(cell["type"], cell)
      max_left = max(max_left, l)
      max_right = max(max_right, r)
      max_left_pins = max(max_left_pins, lp)
      max_right_pins = max(max_right_pins, rp)
    extents[depth] = (max_left, max_right, max_left_pins, max_right_pins)
  return extents


def compute_col_x(col_cells, min_col_gap=COL_GAP):
  """Compute x position for each column depth using pin-count-based clearance."""
  extents = _col_extents(col_cells)
  depths = sorted(col_cells.keys())
  if not depths:
    return {}
  col_x = {}
  # First column starts at X_START
  col_x[depths[0]] = X_START
  for i in range(1, len(depths)):
    prev_d = depths[i - 1]
    curr_d = depths[i]
    _, prev_right, _, prev_right_pins = extents[prev_d]
    curr_left, _, curr_left_pins, _ = extents[curr_d]
    # Pin-count-based gap: additive clearance from both sides
    h_gap = pin_clearance(prev_right_pins) + pin_clearance(curr_left_pins) + H_COL_PAD
    needed = prev_right + h_gap + curr_left
    # Also respect min_col_gap as minimum center-to-center distance
    gap = max(needed, min_col_gap)
    # Snap to grid (multiple of 10)
    gap = ((gap + GRID_UNIT - 1) // GRID_UNIT) * GRID_UNIT
    col_x[curr_d] = col_x[prev_d] + gap
  return col_x



def _place_hl_cells(col_cells, na, bit_nodes, col_x=None):
  """Place high-level (multi-bit) cells. Returns components dict."""
  components = {}

  # Use pre-computed column x positions, or compute them now
  if col_x is None:
    col_x = compute_col_x(col_cells)

  for depth in sorted(col_cells.keys()):
    x_cell = col_x.get(depth, X_START + depth * COL_GAP)
    y_cell = 0

    for cell_name, cell in col_cells[depth]:
      ctype = cell["type"]
      conns = cell["connections"]
      info = _CELL_REGISTRY.get(ctype)
      handler = info.handler if info else None

      if handler:
        y_cell += handler(cell, conns, na, bit_nodes,
                          components, x_cell, y_cell) + V_CELL_PAD
      else:
        _log.warning("unmapped cell type '%s' (%s)", ctype, cell_name)

  return components


# ── Public entry point ────────────────────────────────────────────────────

def place_cells(col_cells, na, bit_nodes, gate_level=False, col_x=None):
  """Map Yosys cells to CircuitVerse components, placed by column.

  Returns components dict (objectType -> [component_dict, ...]).
  """
  if gate_level:
    return place_gate_cells(col_cells, na, bit_nodes, col_x=col_x)
  return _place_hl_cells(col_cells, na, bit_nodes, col_x=col_x)
