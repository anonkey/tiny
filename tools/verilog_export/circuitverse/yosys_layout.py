"""Layout helpers for CircuitVerse: topo sort, port/cell placement.

Supports both gate-level (1-bit $_AND_ etc.) and high-level ($add etc.) cells.
Cell handlers live in components/ — this module provides topo sort and dispatch.
"""

import sys

from circuitverse.components._common import (
  _YOSYS_DFF_PREFIX, CELL_GAP, COL_GAP, X_START, pin_clearance,
  _new_pin, _new_bus_pin, _param_int, _param_bits,
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


# ── High-level cell dispatch ─────────────────────────────────────────────

_HL_DISPATCH = {
  "$and":         place_logic,
  "$or":          place_logic,
  "$xor":         place_logic,
  "$xnor":        place_logic,
  "$not":         place_logic,
  "$mux":         place_mux,
  "$add":         place_add,
  "$sub":         place_sub,
  "$mul":         place_mul,
  "$div":         place_divmod,
  "$mod":         place_divmod,
  "$neg":         place_neg,
  "$shl":         place_shift,
  "$sshl":        place_shift,
  "$shr":         place_shift,
  "$sshr":        place_shift,
  "$eq":          place_eq_ne,
  "$ne":          place_eq_ne,
  "$lt":          place_lt_gt_le_ge,
  "$gt":          place_lt_gt_le_ge,
  "$le":          place_lt_gt_le_ge,
  "$ge":          place_lt_gt_le_ge,
  "$logic_not":   place_logic_not,
  "$logic_and":   place_logic_and_or,
  "$logic_or":    place_logic_and_or,
  "$reduce_and":  place_reduce,
  "$reduce_or":   place_reduce,
  "$reduce_xor":  place_reduce,
  "$reduce_xnor": place_reduce,
  "$reduce_bool": place_reduce,
  "$dff":         place_dff,
  "$dffe":        place_dff,
  "$adff":        place_dff,
  "$adffe":       place_dff,
  "$sdff":        place_dff,
  "$sdffe":       place_dff,
  "$slice":       place_slice,
  "$concat":      place_concat,
  "$mem_v2":      place_mem_v2,
}


# ── Horizontal extent per Yosys cell type ────────────────────────────────
# (left_extent, right_extent) from column center x, including sub-components.
# Values include component body dimensions + sub-component offsets + their body.

def _cell_h_extent(ctype, cell):
  """Return (left, right) reach from column center for a Yosys cell."""
  from circuitverse.components.registry import dimensions, component_width
  # Map Yosys type → main CV component type + sub-component offsets
  _EXTENT = {
    # (cv_type, extra_left, extra_right, cv_params_fn)
    "$and":         ("AndGate",  0,   0),
    "$or":          ("OrGate",   0,   0),
    "$xor":         ("XorGate",  0,   0),
    "$xnor":        ("XnorGate", 0,   0),
    "$not":         ("NotGate",  0,   0),
    "$mux":         ("Multiplexer", 0, 0),
    "$add":         ("Adder",    0,   80),   # splitter at x+60, dim right ~20
    "$sub":         ("ALU",      80,  0),    # ConstantVal at x-60, dim left ~20
    "$mul":         ("verilogMultiplier", 0, 0),
    "$div":         ("verilogDivider", 0, 0),
    "$mod":         ("verilogDivider", 0, 0),
    "$neg":         ("TwoComplement", 0, 0),
    "$shl":         ("verilogShiftLeft", 0, 0),
    "$sshl":        ("verilogShiftLeft", 0, 0),
    "$shr":         ("verilogShiftRight", 0, 0),
    "$sshr":        ("verilogShiftRight", 0, 0),
    "$eq":          ("XnorGate", 0,   140),  # split_reduce: spl at x+60, gate at x+120, dim ~20
    "$ne":          ("XnorGate", 0,   140),
    "$lt":          ("ALU",      80,  140),  # ConstantVal x-60 + splitter x+60 + NotGate x+120
    "$gt":          ("ALU",      80,  140),
    "$le":          ("ALU",      80,  140),
    "$ge":          ("ALU",      80,  140),
    "$logic_not":   ("NorGate",  80,  40),   # split_reduce at x-60/x+20
    "$logic_and":   ("AndGate",  100, 60),   # sub-comps at x-80, main at x+40
    "$logic_or":    ("OrGate",   100, 60),
    "$reduce_and":  ("AndGate",  60,  60),   # split_reduce: spl x-40, gate x+40
    "$reduce_or":   ("OrGate",   60,  60),
    "$reduce_xor":  ("XorGate",  60,  60),
    "$reduce_xnor": ("XnorGate", 60,  60),
    "$reduce_bool": ("OrGate",   60,  60),
    "$dff":         ("DflipFlop", 80, 0),    # ConstantVal/NotGate at x-60
    "$dffe":        ("DflipFlop", 80, 0),
    "$adff":        ("DflipFlop", 80, 0),
    "$adffe":       ("DflipFlop", 80, 0),
    "$sdff":        ("DflipFlop", 80, 0),
    "$sdffe":       ("DflipFlop", 80, 0),
    "$slice":       ("Splitter",  0,  0),
    "$concat":      ("Splitter",  0,  0),
    "$mem_v2":      ("verilogRAM", 0, 0),
    # Gate-level types
    "$_AND_":       ("AndGate",  0, 0),
    "$_OR_":        ("OrGate",   0, 0),
    "$_NOT_":       ("NotGate",  0, 0),
    "$_NAND_":      ("NandGate", 0, 0),
    "$_NOR_":       ("NorGate",  0, 0),
    "$_XOR_":       ("XorGate",  0, 0),
    "$_XNOR_":      ("XnorGate", 0, 0),
    "$_MUX_":       ("Multiplexer", 0, 0),
  }
  # Gate-level DFF types (prefix match)
  if ctype.startswith("$_DFF"):
    return (20, 20)  # DflipFlop: left=20, right=20
  info = _EXTENT.get(ctype)
  if not info:
    return (40, 40)  # fallback
  cv_type, extra_left, extra_right = info
  try:
    # Get main component body dimensions
    params = {}
    if cv_type in ("AndGate", "OrGate", "NandGate", "NorGate", "XorGate", "XnorGate"):
      params["inputLength"] = 2
    dim = dimensions(cv_type, **params)
    left = dim["left"] + extra_left
    right = dim["right"] + extra_right
  except KeyError:
    left = 20 + extra_left
    right = 20 + extra_right
  return (left, right)


def _cell_outward_pins(ctype, cell):
  """Return (left_pins, right_pins) outward-facing horizontal pin counts.

  'Outward' means: leftmost sub-component's left side pin count,
  rightmost sub-component's right side pin count.
  """
  _PINS = {
    # (left_pins, right_pins)
    "$and":         (2, 1),
    "$or":          (2, 1),
    "$xor":         (2, 1),
    "$xnor":        (2, 1),
    "$not":         (1, 1),
    "$mux":         (2, 1),
    "$add":         (3, 2),   # inpA+inpB+carryIn / sum+carryOut
    "$sub":         (0, 1),   # ConstantVal leftmost (0 left), ALU right (1)
    "$mul":         (2, 1),
    "$div":         (2, 2),   # quotient+remainder
    "$mod":         (2, 2),
    "$neg":         (1, 1),
    "$shl":         (2, 1),
    "$sshl":        (2, 1),
    "$shr":         (2, 1),
    "$sshr":        (2, 1),
    "$eq":          (2, 1),   # XnorGate left, reduce gate right
    "$ne":          (2, 1),
    "$lt":          (0, 1),   # ConstantVal leftmost (0), last comp right (1)
    "$gt":          (0, 1),
    "$le":          (0, 1),
    "$ge":          (0, 1),
    "$logic_not":   (1, 1),
    "$logic_and":   (1, 1),
    "$logic_or":    (1, 1),
    "$reduce_and":  (1, 1),
    "$reduce_or":   (1, 1),
    "$reduce_xor":  (1, 1),
    "$reduce_xnor": (1, 1),
    "$reduce_bool": (1, 1),
    "$dff":         (0, 2),   # ConstantVal leftmost (0), DFF right (qOutput+qInvOutput)
    "$dffe":        (0, 2),
    "$adff":        (0, 2),
    "$adffe":       (0, 2),
    "$sdff":        (0, 2),
    "$sdffe":       (0, 2),
    "$concat":      (2, 1),   # Splitter joining: 2 inputs left, 1 output right
    "$mem_v2":      (4, 1),   # approximate: many left, read data right
    # Gate-level types
    "$_AND_":       (2, 1),
    "$_OR_":        (2, 1),
    "$_NOT_":       (1, 1),
    "$_NAND_":      (2, 1),
    "$_NOR_":       (2, 1),
    "$_XOR_":       (2, 1),
    "$_XNOR_":      (2, 1),
    "$_MUX_":       (2, 1),   # 2 data + 1 select, but select is bottom
  }
  # Gate-level DFF types (prefix match)
  if ctype.startswith("$_DFF"):
    return (2, 2)  # dInp+clockInp left, qOutput+qInvOutput right
  pins = _PINS.get(ctype)
  if pins:
    return pins
  # $slice: Splitter splitting — right pins = number of output groups
  if ctype == "$slice":
    a_bw = _param_int(cell, "A_WIDTH", 1) if cell else 1
    y_bw = _param_int(cell, "Y_WIDTH", 1) if cell else 1
    offset = _param_int(cell, "OFFSET", 0) if cell else 0
    groups = 1  # Y output
    if offset > 0:
      groups += 1
    if a_bw - offset - y_bw > 0:
      groups += 1
    return (1, groups)
  return (1, 1)  # fallback


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


def compute_col_x(col_cells):
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
    h_gap = pin_clearance(prev_right_pins) + pin_clearance(curr_left_pins) + 20
    needed = prev_right + h_gap + curr_left
    # Also respect COL_GAP as minimum center-to-center distance
    gap = max(needed, COL_GAP)
    # Snap to grid (multiple of 10)
    gap = ((gap + 9) // 10) * 10
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
      handler = _HL_DISPATCH.get(ctype)

      if handler:
        y_cell += handler(cell_name, cell, conns, na, bit_nodes,
                          components, x_cell, y_cell)
      else:
        print(f"  warning: unmapped cell type '{ctype}' ({cell_name})",
              file=sys.stderr)

  return components


# ── Public entry point ────────────────────────────────────────────────────

def place_cells(col_cells, na, bit_nodes, gate_level=False, col_x=None):
  """Map Yosys cells to CircuitVerse components, placed by column.

  Returns components dict (objectType -> [component_dict, ...]).
  """
  if gate_level:
    return place_gate_cells(col_cells, na, bit_nodes, col_x=col_x)
  return _place_hl_cells(col_cells, na, bit_nodes, col_x=col_x)
