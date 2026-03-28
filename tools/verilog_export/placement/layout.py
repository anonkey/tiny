"""Layout helpers for CircuitVerse: topo sort, port/cell placement.

Supports both gate-level (1-bit $_AND_ etc.) and high-level ($add etc.) cells.
Cell handlers live in synthesis/gates/ — this module provides topo sort and dispatch.
"""
from __future__ import annotations

import logging
from typing import Callable, NamedTuple

from common.types import CompDict, CVCustomData, CVSubCircuit, CompMap, BitNodes, YosysModule, YosysCell, YosysConns, SubScopeInfo, PortInfo, CellEntry, ColCells
from common.node_alloc import _CVNodeAlloc

_log: logging.Logger = logging.getLogger(__name__)

from common.constants import (
  _YOSYS_DFF_PREFIX, COL_GAP, X_START, H_COL_PAD, V_CELL_PAD, GATE_V_CELL_PAD,
  GRID_UNIT, pin_clearance, _new_pin, _new_bus_pin, _param_int, _param_bits,
  _adapt_width, _maybe_invert,
)
from synthesis.gates import (
  place_logic, place_mux,
  place_add, place_sub, place_mul, place_divmod, place_neg,
  place_shift,
  place_eq_ne, place_lt_gt_le_ge,
  place_reduce, place_logic_not, place_logic_and_or,
  place_dff,
  place_slice, place_concat, place_cv_splitter,
  place_mem_v2, place_memrd,
  place_gate_logic, place_gate_mux, place_gate_dff,
)


# ── Unified cell registry ─────────────────────────────────────────────────
# Single source of truth for handler, extent, and pin info per Yosys cell type.
# handler:     place_* function
# cv_type:     CircuitVerse component type (for dimension lookup)
# extra_left:  sub-component offset added to left extent
# extra_right: sub-component offset added to right extent
# left_pins:   outward-facing pins on left (None → compute dynamically)
# right_pins:  outward-facing pins on right (None → compute dynamically)
# v_pad:       vertical padding after this cell

class CellInfo(NamedTuple):
    handler: Callable[..., int]
    cv_type: str
    extra_left: int
    extra_right: int
    left_pins: int | None
    right_pins: int | None
    v_pad: int

_CELL_REGISTRY: dict[str, CellInfo] = {
  # ── Logic gates (high-level) ──
  "$and":         CellInfo(place_logic,      "AndGate",       0,   0,   2, 1, V_CELL_PAD),
  "$or":          CellInfo(place_logic,      "OrGate",        0,   0,   2, 1, V_CELL_PAD),
  "$xor":         CellInfo(place_logic,      "XorGate",       0,   0,   2, 1, V_CELL_PAD),
  "$xnor":        CellInfo(place_logic,      "XnorGate",      0,   0,   2, 1, V_CELL_PAD),
  "$not":         CellInfo(place_logic,      "NotGate",       0,   0,   1, 1, V_CELL_PAD),
  "$mux":         CellInfo(place_mux,        "Multiplexer",   0,   0,   2, 1, V_CELL_PAD),
  # ── Arithmetic ──
  "$add":         CellInfo(place_add,        "Adder",         0,   80,  3, 2, V_CELL_PAD),
  "$sub":         CellInfo(place_sub,        "ALU",           80,  0,   0, 1, V_CELL_PAD),
  "$mul":         CellInfo(place_mul,        "verilogMultiplier", 0, 0, 2, 1, V_CELL_PAD),
  "$div":         CellInfo(place_divmod,     "verilogDivider", 0,  0,   2, 2, V_CELL_PAD),
  "$mod":         CellInfo(place_divmod,     "verilogDivider", 0,  0,   2, 2, V_CELL_PAD),
  "$neg":         CellInfo(place_neg,        "TwoComplement", 0,   0,   1, 1, V_CELL_PAD),
  # ── Shifts ──
  "$shl":         CellInfo(place_shift,      "verilogShiftLeft",  0, 0, 2, 1, V_CELL_PAD),
  "$sshl":        CellInfo(place_shift,      "verilogShiftLeft",  0, 0, 2, 1, V_CELL_PAD),
  "$shr":         CellInfo(place_shift,      "verilogShiftRight", 0, 0, 2, 1, V_CELL_PAD),
  "$sshr":        CellInfo(place_shift,      "verilogShiftRight", 0, 0, 2, 1, V_CELL_PAD),
  # ── Comparisons ──
  "$eq":          CellInfo(place_eq_ne,      "XnorGate",      0,   140, 2, 1, V_CELL_PAD),
  "$ne":          CellInfo(place_eq_ne,      "XnorGate",      0,   140, 2, 1, V_CELL_PAD),
  "$lt":          CellInfo(place_lt_gt_le_ge,"ALU",           80,  140, 0, 1, V_CELL_PAD),
  "$gt":          CellInfo(place_lt_gt_le_ge,"ALU",           80,  140, 0, 1, V_CELL_PAD),
  "$le":          CellInfo(place_lt_gt_le_ge,"ALU",           80,  140, 0, 1, V_CELL_PAD),
  "$ge":          CellInfo(place_lt_gt_le_ge,"ALU",           80,  140, 0, 1, V_CELL_PAD),
  # ── Reductions ──
  "$logic_not":   CellInfo(place_logic_not,  "NorGate",       80,  40,  1, 1, V_CELL_PAD),
  "$logic_and":   CellInfo(place_logic_and_or,"AndGate",      100, 60,  1, 1, V_CELL_PAD),
  "$logic_or":    CellInfo(place_logic_and_or,"OrGate",       100, 60,  1, 1, V_CELL_PAD),
  "$reduce_and":  CellInfo(place_reduce,     "AndGate",       60,  60,  1, 1, V_CELL_PAD),
  "$reduce_or":   CellInfo(place_reduce,     "OrGate",        60,  60,  1, 1, V_CELL_PAD),
  "$reduce_xor":  CellInfo(place_reduce,     "XorGate",       60,  60,  1, 1, V_CELL_PAD),
  "$reduce_xnor": CellInfo(place_reduce,     "XnorGate",      60,  60,  1, 1, V_CELL_PAD),
  "$reduce_bool": CellInfo(place_reduce,     "OrGate",        60,  60,  1, 1, V_CELL_PAD),
  # ── DFFs ──
  "$dff":         CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2, V_CELL_PAD),
  "$dffe":        CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2, V_CELL_PAD),
  "$adff":        CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2, V_CELL_PAD),
  "$adffe":       CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2, V_CELL_PAD),
  "$sdff":        CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2, V_CELL_PAD),
  "$sdffe":       CellInfo(place_dff,        "DflipFlop",     80,  0,   0, 2, V_CELL_PAD),
  # ── Bus ops ──
  "$slice":       CellInfo(place_slice,      "Splitter",      0,   0,   1, None, V_CELL_PAD),
  "$concat":      CellInfo(place_concat,     "Splitter",      0,   0,   2, 1, V_CELL_PAD),
  "$cv_splitter": CellInfo(place_cv_splitter,"Splitter",      0,   0,   2, 2, V_CELL_PAD),
  "$mem_v2":      CellInfo(place_mem_v2,     "verilogRAM",    0,   0,   4, 1, V_CELL_PAD),
  "$memrd":       CellInfo(place_memrd,     "EEPROM",        0,   0,   1, 1, V_CELL_PAD),
  # ── Gate-level types ──
  "$_AND_":       CellInfo(place_gate_logic, "AndGate",      0, 0, 2, 1, GATE_V_CELL_PAD),
  "$_OR_":        CellInfo(place_gate_logic, "OrGate",       0, 0, 2, 1, GATE_V_CELL_PAD),
  "$_NOT_":       CellInfo(place_gate_logic, "NotGate",      0, 0, 1, 1, GATE_V_CELL_PAD),
  "$_NAND_":      CellInfo(place_gate_logic, "NandGate",     0, 0, 2, 1, GATE_V_CELL_PAD),
  "$_NOR_":       CellInfo(place_gate_logic, "NorGate",      0, 0, 2, 1, GATE_V_CELL_PAD),
  "$_XOR_":       CellInfo(place_gate_logic, "XorGate",      0, 0, 2, 1, GATE_V_CELL_PAD),
  "$_XNOR_":      CellInfo(place_gate_logic, "XnorGate",     0, 0, 2, 1, GATE_V_CELL_PAD),
  "$_MUX_":       CellInfo(place_gate_mux,   "Multiplexer",  0, 0, 2, 1, GATE_V_CELL_PAD),
}

# Fallback for $_DFF* variants (many combinations, not enumerable)
_GATE_DFF_INFO: CellInfo = CellInfo(place_gate_dff, "DflipFlop", 0, 0, 2, 2, GATE_V_CELL_PAD)


def _lookup_cell_info(ctype: str) -> CellInfo | None:
  """Look up CellInfo from registry, with DFF prefix fallback."""
  info = _CELL_REGISTRY.get(ctype)
  if info is None and ctype.startswith(_YOSYS_DFF_PREFIX):
    return _GATE_DFF_INFO
  return info


# ── Topological sort ───────────────────────────────────────────────────────

def topo_sort_cells(ymod: YosysModule) -> tuple[list[CellEntry], ColCells, dict[str, int]]:
  """Extract cells, compute depth, return (sorted_cells, col_cells).

  Uses port_directions from Yosys JSON to automatically determine
  input/output ports for any cell type.
  """
  cells: list[CellEntry] = [(n, c) for n, c in ymod.get("cells", {}).items()
           if c["type"] != "$scopeinfo"]

  bit_producer: dict[int, str] = {}
  for cell_name, cell in cells:
    dirs = cell.get("port_directions", {})
    for pn, d in dirs.items():
      if d == "output":
        for b in cell["connections"].get(pn, []):
          if not isinstance(b, str):
            bit_producer[b] = cell_name

  cell_depth: dict[str, int] = {}
  cell_by_name: dict[str, YosysCell] = {n: c for n, c in cells}

  def _depth(cname: str, visiting: set[str] | None = None) -> int:
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

  sorted_cells: list[CellEntry] = sorted(cells, key=lambda nc: (cell_depth[nc[0]],
                                                 cells.index(nc)))
  col_cells: ColCells = {}
  for cname, cell in sorted_cells:
    d = cell_depth[cname]
    col_cells.setdefault(d, []).append((cname, cell))

  return sorted_cells, col_cells, cell_depth


# ── Horizontal extent per Yosys cell type ────────────────────────────────

def _cell_h_extent(ctype: str, cell: YosysCell, sub_scope_ids: dict[str, SubScopeInfo] | None = None) -> tuple[int, int]:
  """Return (left, right) reach from column center for a Yosys cell."""
  from synthesis.gates.registry import dimensions
  # Subcircuit types — extent is half layout width on each side
  if sub_scope_ids and ctype in sub_scope_ids:
    hw = sub_scope_ids[ctype].get("layout_w", 100) // 2
    return (hw, hw)
  info = _lookup_cell_info(ctype)
  if not info:
    _log.error("_cell_h_extent: unknown cell type '%s', using fallback (40, 40)", ctype)
    raise ValueError(f"Unknown cell type '{ctype}'")
  cv_type = info.cv_type
  try:
    params = {}
    # TODO: chek if hlsynt can do 3 gate door
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


def _cell_outward_pins(ctype: str, cell: YosysCell, sub_scope_ids: dict[str, SubScopeInfo] | None = None) -> tuple[int, int]:
  """Return (left_pins, right_pins) outward-facing horizontal pin counts.

  'Outward' means: leftmost sub-component's left side pin count,
  rightmost sub-component's right side pin count.
  """
  # Subcircuit types — pin count from port_info
  if sub_scope_ids and ctype in sub_scope_ids:
    pi = sub_scope_ids[ctype].get("port_info", {})
    n_in = sum(1 for p in pi.values() if p["direction"] == "input")
    n_out = sum(1 for p in pi.values() if p["direction"] == "output")
    return (max(n_in, 1), max(n_out, 1))
  info = _lookup_cell_info(ctype)
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


def _col_extents(col_cells: ColCells, sub_scope_ids: dict[str, SubScopeInfo] | None = None) -> dict[int, tuple[int, int, int, int]]:
  """Compute max (left, right) extent and outward pin counts per column."""
  extents: dict[int, tuple[int, int, int, int]] = {}
  for depth, cells in col_cells.items():
    max_left = 0
    max_right = 0
    max_left_pins = 0
    max_right_pins = 0
    for _, cell in cells:
      l, r = _cell_h_extent(cell["type"], cell, sub_scope_ids)
      lp, rp = _cell_outward_pins(cell["type"], cell, sub_scope_ids)
      max_left = max(max_left, l)
      max_right = max(max_right, r)
      max_left_pins = max(max_left_pins, lp)
      max_right_pins = max(max_right_pins, rp)
    extents[depth] = (max_left, max_right, max_left_pins, max_right_pins)
  return extents


def compute_col_x(col_cells: ColCells, min_col_gap: int = COL_GAP, sub_scope_ids: dict[str, SubScopeInfo] | None = None) -> dict[int, int]:
  """Compute x position for each column depth using pin-count-based clearance."""
  extents: dict[int, tuple[int, int, int, int]] = _col_extents(col_cells, sub_scope_ids)
  depths: list[int] = sorted(col_cells.keys())
  if not depths:
    return {}
  col_x: dict[int, int] = {}
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



def _place_subcircuit(cell_name: str, cell: YosysCell, na: _CVNodeAlloc, bit_nodes: BitNodes, sub_scope_ids: dict[str, SubScopeInfo],
                      x_center: int, y_cell: int, cv_subcircuits: list[CVSubCircuit], sc_comps: list[CompDict]) -> tuple[int, int]:
  """Place a single subcircuit instance. Returns (height, n_max)."""
  ctype: str = cell["type"]
  sid: SubScopeInfo = sub_scope_ids[ctype]
  port_info: dict[str, PortInfo] = sid["port_info"]
  layout_w: int = sid.get("layout_w", 100)
  dirs: dict[str, str] = cell.get("port_directions", {})
  conns: dict[str, list[int | str]] = cell["connections"]

  input_nodes: list[int] = []
  output_nodes: list[int] = []

  # Allocate input ports first, then outputs, matching the
  # sub-scope's Input/Output declaration order (port_info order).
  for pname in port_info:
    d = dirs.get(pname)
    if d != "input":
      continue
    bits = conns.get(pname, [])
    bw = len(bits)
    pi = port_info.get(pname, {"x": 0, "y": 20})
    nid = na.alloc(pi["x"], pi["y"], 0, bw)
    input_nodes.append(nid)
    for b in bits:
      if not isinstance(b, str):
        bit_nodes.setdefault(b, []).append(nid)
  for pname in port_info:
    d = dirs.get(pname)
    if d != "output":
      continue
    bits = conns.get(pname, [])
    bw = len(bits)
    pi = port_info.get(pname, {"x": 0, "y": 20})
    nid = na.alloc(pi["x"], pi["y"], 1, bw)
    output_nodes.append(nid)
    for b in bits:
      if not isinstance(b, str):
        bit_nodes.setdefault(b, []).append(nid)

  n_max = max(len(input_nodes), len(output_nodes), 1)
  h = 20 * n_max + 40

  # SubCircuit origin is top-left; col_x is center, so offset by half width
  sc_x = x_center - layout_w // 2

  sc_dict = {
    "x": sc_x, "y": y_cell,
    "id": sid["scope_id"],
    "label": cell_name,
    "labelDirection": "RIGHT",
    "inputNodes": input_nodes,
    "outputNodes": output_nodes,
    "version": "2.0",
  }
  cv_subcircuits.append(sc_dict)

  # Synthetic component dict so the router can block the body
  all_nids = input_nodes + output_nodes
  sc_comps.append(CompDict(
    x=sc_x, y=y_cell,
    objectType="",
    customData=CVCustomData(
      nodes={"pins": all_nids},
      _sc_dimensions={
        "left": 0, "right": layout_w,
        "up": 0, "down": h,
      },
    ),
  ))

  return h, n_max


def _place_cells_impl(col_cells: ColCells, na: _CVNodeAlloc, bit_nodes: BitNodes, col_x: dict[int, int] | None = None, sub_scope_ids: dict[str, SubScopeInfo] | None = None,
                      default_v_pad: int = V_CELL_PAD) -> tuple[CompMap, dict[str, tuple[int, int]], list[CVSubCircuit], list[CompDict]]:
  """Place cells (gate-level or high-level). Returns (components, cell_positions,
  cv_subcircuits, sc_comps)."""
  components: CompMap = {}
  cell_positions: dict[str, tuple[int, int]] = {}
  cv_subcircuits: list[CVSubCircuit] = []
  sc_comps: list[CompDict] = []

  # Use pre-computed column x positions, or compute them now
  if col_x is None:
    col_x = compute_col_x(col_cells, sub_scope_ids=sub_scope_ids)

  for depth in sorted(col_cells.keys()):
    x_cell = col_x.get(depth, X_START + depth * COL_GAP)
    y_cell = 0

    for cell_name, cell in col_cells[depth]:
      ctype = cell["type"]
      cell_positions[cell_name] = (x_cell, y_cell)

      # Subcircuit cell
      if sub_scope_ids and ctype in sub_scope_ids:
        h, n_max = _place_subcircuit(cell_name, cell, na, bit_nodes,
                                     sub_scope_ids, x_cell, y_cell,
                                     cv_subcircuits, sc_comps)
        y_cell += h + pin_clearance(n_max) + default_v_pad
        continue

      info = _lookup_cell_info(ctype)
      handler = info.handler if info else None

      if handler:
        conns = cell["connections"]
        v_pad = info.v_pad if info else default_v_pad
        y_cell += handler(cell, conns, na, bit_nodes,
                          components, x_cell, y_cell) + v_pad
      else:
        _log.warning("unmapped cell type '%s' (%s)", ctype, cell_name)

  return components, cell_positions, cv_subcircuits, sc_comps


# ── Public entry point ────────────────────────────────────────────────────

def place_cells(col_cells: ColCells, na: _CVNodeAlloc, bit_nodes: BitNodes, gate_level: bool = False, col_x: dict[int, int] | None = None,
                sub_scope_ids: dict[str, SubScopeInfo] | None = None) -> tuple[CompMap, dict[str, tuple[int, int]], list[CVSubCircuit], list[CompDict]]:
  """Map Yosys cells to CircuitVerse components, placed by column.

  Returns (components, cell_positions, cv_subcircuits, sc_comps).
  components: dict (objectType -> [component_dict, ...])
  cell_positions: dict (cell_name -> (x, y))
  cv_subcircuits: list of SubCircuit dicts (empty for flat exports)
  sc_comps: list of synthetic component dicts for router blocking
  """
  default_v_pad: int = GATE_V_CELL_PAD if gate_level else V_CELL_PAD
  return _place_cells_impl(col_cells, na, bit_nodes, col_x=col_x,
                           sub_scope_ids=sub_scope_ids,
                           default_v_pad=default_v_pad)
