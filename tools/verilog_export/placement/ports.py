"""Port placement for CircuitVerse: Input/Output components.

Ports are placed **outside** the bounding box of all logic cells:
  - Inputs to the left of the bbox
  - Outputs to the right of the bbox
Each port aligns vertically with its target cell (leftmost consumer
for inputs, rightmost producer for outputs).

Width-adaptation splitters are inserted by the splitter_pass before
placement — this module only creates Input/Output components.

All positions snap to 10×10 grid.
"""
from __future__ import annotations

import logging
from typing import Any

from common.node_alloc import _CVNodeAlloc
from common.types import CompDict, BitNodes, YosysModule

_log: logging.Logger = logging.getLogger(__name__)

from common.constants import _new_pin, _new_bus_pin, CELL_GAP, COL_GAP, X_START, pin_clearance, CTOR_PARAMS_KEY, GRID_UNIT
from synthesis.gates.registry import pin_pos, dimensions


def _find_port_target(port_bits: list[int | str], direction: str, ymod: YosysModule, cell_depth: dict[str, int]) -> str | None:
    """Find the target cell for proximity placement.

    For inputs: returns cell_name of leftmost (min depth) consumer.
    For outputs: returns cell_name of rightmost (max depth) producer.
    Returns None if no connected cell found.
    """
    cells: dict[str, Any] = ymod.get("cells", {})
    port_bits_set: set[int] = set(b for b in port_bits if not isinstance(b, str))
    if not port_bits_set:
        return None

    target_dir: str = "input" if direction == "input" else "output"
    best_cell: str | None = None
    best_depth: int | None = None

    for cell_name, cell in cells.items():  # type: str, dict[str, Any]
        if cell.get("type") == "$scopeinfo":
            continue
        if cell_name not in cell_depth:
            continue
        dirs: dict[str, str] = cell.get("port_directions", {})
        conns: dict[str, list[int | str]] = cell.get("connections", {})
        for pname, d in dirs.items():  # type: str, str
            if d != target_dir:
                continue
            for b in conns.get(pname, []):
                if isinstance(b, str) or b not in port_bits_set:
                    continue
                d_val: int = cell_depth[cell_name]
                if direction == "input":
                    if best_depth is None or d_val < best_depth:
                        best_depth = d_val
                        best_cell = cell_name
                else:
                    if best_depth is None or d_val > best_depth:
                        best_depth = d_val
                        best_cell = cell_name
                break  # found a match for this port on this cell

    _log.debug("_find_port_target: bits=%s dir=%s -> %s (depth=%s)",
               port_bits[:3], direction, best_cell, best_depth)
    return best_cell


def _snap(x: int) -> int:
    """Snap x to 10-unit grid (round up)."""
    return ((x + GRID_UNIT - 1) // GRID_UNIT) * GRID_UNIT


def compute_bbox(col_cells: dict[int, list[tuple[str, dict[str, Any]]]], col_x: dict[int, int], cell_positions: dict[str, tuple[int, int]], sc_comps: list[CompDict],
                 sub_scope_ids: dict[str, dict[str, Any]] | None = None) -> tuple[int, int, int, int]:
    """Compute bounding box of all placed non-port components.

    Returns (left, top, right, bottom) with padding for routing clearance.
    """
    from placement.layout import _col_extents
    if not col_x:
        # No cells — return a default box
        return (X_START, 0, X_START + 100, 100)

    extents: dict[int, tuple[int, int]] = _col_extents(col_cells, sub_scope_ids)

    # Horizontal bounds from column extents
    left: int = min(col_x[d] - extents[d][0] for d in col_x)
    right: int = max(col_x[d] + extents[d][1] for d in col_x)

    # Vertical bounds from cell positions + estimated heights
    top: int = 0
    bottom: int = 0
    for cell_name, (cx, cy) in cell_positions.items():
        bottom = max(bottom, cy + CELL_GAP)  # conservative height estimate

    # Also account for subcircuit body extents
    for sc in sc_comps:
        sx: int = sc["x"]
        sy: int = sc["y"]
        dims: dict[str, Any] = sc["customData"].get("_sc_dimensions", {})
        sc_right: int = sx + dims.get("right", 100)
        sc_bottom: int = sy + dims.get("down", 60)
        right = max(right, sc_right)
        bottom = max(bottom, sc_bottom)

    # Add padding so ports don't sit flush against cells
    pad: int = pin_clearance(2)
    _log.debug("compute_bbox: raw=(%d, %d, %d, %d) pad=%d",
               left, top, right, bottom, pad)
    return (left - pad, top, right + pad, bottom)


def place_ports(ymod: YosysModule, na: _CVNodeAlloc, bit_nodes: BitNodes, col_cells: dict[int, list[tuple[str, dict[str, Any]]]], col_x: dict[int, int] | None = None,
                cell_depth: dict[str, int] | None = None, cell_positions: dict[str, tuple[int, int]] | None = None, bbox: tuple[int, int, int, int] | None = None,
                layout_w: int = 100) -> tuple[list[CompDict], list[CompDict], list[CompDict], int, int]:
    """Create Input/Output CV components with splitters for multi-bit ports.

    Ports are placed outside the bounding box, aligned with their target cell's y.
    Returns (cv_inputs, cv_outputs, cv_splitters, y_in, y_out).
    """
    if col_x is None:
        col_x = {}
    if cell_depth is None:
        cell_depth = {}
    if cell_positions is None:
        cell_positions = {}
    if bbox is None:
        bbox = (0, 0, X_START + 100, 100)

    bbox_left: int
    bbox_top: int
    bbox_right: int
    bbox_bottom: int
    bbox_left, bbox_top, bbox_right, bbox_bottom = bbox

    # Find max bitwidths for body/clearance sizing
    max_in_bw: int = max((len(p["bits"]) for p in ymod.get("ports", {}).values()
                     if p["direction"] == "input"), default=1)
    max_out_bw: int = max((len(p["bits"]) for p in ymod.get("ports", {}).values()
                     if p["direction"] == "output"), default=1)
    # Compute fixed x columns for inputs (left of bbox) and outputs (right of bbox)
    inp_body_right: int = max_in_bw * 10  # Input body right edge (from pin_pos formula)
    inp_clearance: int = max_in_bw * 20 + 20

    inp_x: int = _snap(bbox_left - inp_clearance - inp_body_right)

    out_body_left: int = max_out_bw * 10
    out_clearance: int = max_out_bw * 20 + 20

    out_x: int = _snap(bbox_right + out_clearance + out_body_left)

    _log.debug("place_ports: bbox=(%d,%d,%d,%d) inp_x=%d out_x=%d",
               bbox_left, bbox_top, bbox_right, bbox_bottom,
               inp_x, out_x)

    cv_inputs: list[CompDict] = []
    cv_outputs: list[CompDict] = []
    cv_splitters: list[CompDict] = []
    # Track used y-ranges per side to avoid overlaps
    # Each entry is (y_start, y_end)
    used_left: list[tuple[int, int]] = []
    used_right: list[tuple[int, int]] = []
    layout_pin_y_in: int = 40
    layout_pin_y_out: int = 40

    def _find_free_y(desired_y: int, height: int, used_ranges: list[tuple[int, int]]) -> int:
        """Find the nearest free y position starting from desired_y."""
        y: int = _snap(desired_y)
        # Sort ranges by start
        ranges: list[tuple[int, int]] = sorted(used_ranges)
        for ys, ye in ranges:
            if y + height <= ys or y >= ye:
                continue  # no overlap
            # Overlap — push below this range
            y = _snap(ye)
        return y

    for port_name, port_info in ymod.get("ports", {}).items():  # type: str, dict[str, Any]
        direction: str = port_info["direction"]
        bits: list[int | str] = port_info["bits"]
        bw: int = len(bits)
        port_height: int = max(bw * 20 + 20, CELL_GAP)

        # Find target cell for proximity placement
        target_cell: str | None = _find_port_target(bits, direction, ymod, cell_depth)

        if direction == "input":
            # Compute y position — align with target cell, avoid overlaps
            desired_y: int
            if target_cell and target_cell in cell_positions:
                _, desired_y = cell_positions[target_cell]
            else:
                desired_y = used_left[-1][1] if used_left else 0
            port_y: int = _find_free_y(desired_y, port_height, used_left)
            used_left.append((port_y, port_y + port_height))

            inp_px: int
            inp_py: int
            inp_px, inp_py = pin_pos("Input", "output1", bitWidth=bw)
            out_node: int
            if bw == 1:
                out_node = _new_pin(na, bit_nodes, bits[0], 1, 1, rx=inp_px, ry=inp_py)
            else:
                out_node = _new_bus_pin(na, bit_nodes, bits, 1, bw, rx=inp_px, ry=inp_py)

            cv_inputs.append({
                "x": inp_x, "y": port_y,
                "objectType": "Input",
                "label": port_name,
                "direction": "RIGHT",
                "labelDirection": "LEFT",
                "propagationDelay": 0,
                "customData": {
                    "nodes": {"output1": out_node},
                    "values": {"state": 0},
                    CTOR_PARAMS_KEY: ["RIGHT", str(bw) if bw > 1 else 1,
                        {"x": 0, "y": layout_pin_y_in, "id": f"p_{port_name}"}],
                },
            })
            _log.debug("place_ports: input '%s' at (%d, %d) target=%s",
                        port_name, inp_x, port_y, target_cell)
            layout_pin_y_in += 20

        else:
            # Compute y position — align with target cell, avoid overlaps
            if target_cell and target_cell in cell_positions:
                _, desired_y = cell_positions[target_cell]
            else:
                desired_y = used_right[-1][1] if used_right else 0
            port_y = _find_free_y(desired_y, port_height, used_right)
            used_right.append((port_y, port_y + port_height))

            out_px: int
            out_py: int
            out_px, out_py = pin_pos("Output", "inp1", bitWidth=bw)
            inp_node: int
            if bw == 1:
                inp_node = _new_pin(na, bit_nodes, bits[0], 0, 1, rx=out_px, ry=out_py)
            else:
                inp_node = _new_bus_pin(na, bit_nodes, bits, 0, bw, rx=out_px, ry=out_py)

            cv_outputs.append({
                "x": out_x, "y": port_y,
                "objectType": "Output",
                "label": port_name,
                "direction": "LEFT",
                "labelDirection": "RIGHT",
                "propagationDelay": 0,
                "customData": {
                    "nodes": {"inp1": inp_node},
                    CTOR_PARAMS_KEY: ["LEFT", str(bw) if bw > 1 else 1,
                        {"x": layout_w, "y": layout_pin_y_out, "id": f"p_{port_name}"}],
                },
            })
            _log.debug("place_ports: output '%s' at (%d, %d) target=%s",
                        port_name, out_x, port_y, target_cell)
            layout_pin_y_out += 20

    # Compute overall y extents for layout height calculation
    y_in: int = max((c["y"] + CELL_GAP for c in cv_inputs), default=0)
    y_out: int = max((c["y"] + CELL_GAP for c in cv_outputs), default=0)

    return cv_inputs, cv_outputs, cv_splitters, y_in, y_out
