"""Layout helpers for CircuitVerse: topo sort, port/cell placement.

Supports both gate-level (1-bit $_AND_ etc.) and high-level ($add etc.) cells.
Cell handlers live in components/ — this module provides topo sort and dispatch.
"""

import sys

from components._common import (
  _YOSYS_DFF_PREFIX, CELL_GAP, COL_GAP, X_START,
  _new_pin, _new_bus_pin, _param_int, _param_bits,
  _adapt_width, _maybe_invert,
)
from components import (
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


def _place_hl_cells(col_cells, na, bit_nodes):
  """Place high-level (multi-bit) cells. Returns components dict."""
  components = {}

  for depth in sorted(col_cells.keys()):
    x_cell = X_START + depth * COL_GAP
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

def place_cells(col_cells, na, bit_nodes, gate_level=False):
  """Map Yosys cells to CircuitVerse components, placed by column.

  Returns components dict (objectType -> [component_dict, ...]).
  """
  if gate_level:
    return place_gate_cells(col_cells, na, bit_nodes)
  return _place_hl_cells(col_cells, na, bit_nodes)
