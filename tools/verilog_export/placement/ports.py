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
from common.types import CompDict, CVCustomData, BitNodes, YosysModule

_log: logging.Logger = logging.getLogger(__name__)

from common.constants import _new_pin, _new_bus_pin, CELL_GAP, COL_GAP, X_START, pin_clearance, GRID_UNIT
from synthesis.gates.registry import pin_pos, dimensions


class _PortSide:
    def __init__(self, direction: str, inp_x: int, out_x: int, layout_w: int,
                 cv_inputs: list[CompDict], cv_outputs: list[CompDict],
                 used_left: list[tuple[int, int]], used_right: list[tuple[int, int]],
                 layout_pin_y_in: int, layout_pin_y_out: int) -> None:
        is_input           = direction == "input"
        self.obj_type      = "Input"   if is_input else "Output"
        self.cv_list       = cv_inputs if is_input else cv_outputs
        self.used          = used_left if is_input else used_right
        self.x             = inp_x     if is_input else out_x
        self.cv_dir        = "RIGHT"   if is_input else "LEFT"
        self.label_dir     = "LEFT"    if is_input else "RIGHT"
        self.pin_name      = "output1" if is_input else "inp1"
        self.node_is_output= 1         if is_input else 0
        self.layout_pin_x  = 0         if is_input else layout_w
        self.layout_pin_y  = layout_pin_y_in if is_input else layout_pin_y_out


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
    if x % GRID_UNIT != 0:
        raise ValueError(f"Expected x to be multiple of GRID_UNIT={GRID_UNIT}, got {x}")
    return -((-x) // GRID_UNIT) * GRID_UNIT


def compute_bbox(col_cells: dict[int, list[tuple[str, dict[str, Any]]]], col_x: dict[int, int], cell_positions: dict[str, tuple[int, int]], sc_comps: list[CompDict],
                 sub_scope_ids: dict[str, dict[str, Any]] | None = None) -> tuple[int, int, int, int]:
    """Compute bounding box of all placed non-port components.

    Returns (left, top, right, bottom) with padding for routing clearance.
    """
    from placement.layout import _col_extents
    # TODO: raise
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
        sx: int = sc.x
        sy: int = sc.y
        dims: dict[str, int] | None = sc.customData._sc_dimensions
        sc_right: int = sx + (dims.get("right", 100) if dims else 100)
        sc_bottom: int = sy + (dims.get("down", 60) if dims else 60)
        right = max(right, sc_right)
        bottom = max(bottom, sc_bottom)

    # Add padding so ports don't sit flush against cells
    pad: int = pin_clearance(2)
    _log.debug("compute_bbox: raw=(%d, %d, %d, %d) pad=%d",
               left, top, right, bottom, pad)
    return (left - pad, top, right + pad, bottom)


def place_ports(
        ymod: YosysModule,
        na: _CVNodeAlloc,
        bit_nodes: BitNodes,
        col_cells: dict[int, list[tuple[str, dict[str, Any]]]],
        col_x: dict[int, int] | None = None,
        cell_depth: dict[str, int] | None = None,
        cell_positions: dict[str, tuple[int, int]] | None = None,
        bbox: tuple[int, int, int, int] | None = None,
        layout_w: int = 100
    ) -> tuple[list[CompDict], list[CompDict], list[CompDict], int, int]:
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
    # TODO: raise
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

    _log.debug("snap: raw=(%d, %d, %d, %d) pad=%d",
               bbox_right , out_clearance , out_body_left)
    out_x: int = _snap(bbox_right + out_clearance + out_body_left)

    _log.debug("place_ports: max_in_bw=%d max_out_bw=%d inp_body_right=%d inp_clearance=%d out_body_left=%d out_clearance=%d",
               max_in_bw, max_out_bw, inp_body_right, inp_clearance, out_body_left, out_clearance)
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

        # TODO: Collisions check Find target cell for proximity placement
        target_cell: str | None = _find_port_target(bits, direction, ymod, cell_depth)

        side = _PortSide(direction, inp_x, out_x, layout_w,
                         cv_inputs, cv_outputs, used_left, used_right,
                         layout_pin_y_in, layout_pin_y_out)

        desired_y: int = (cell_positions[target_cell][1]
                          if target_cell and target_cell in cell_positions
                          else (side.used[-1][1] if side.used else 0))
        port_y: int = _find_free_y(desired_y, port_height, side.used)
        side.used.append((port_y, port_y + port_height))

        px: int
        py: int
        px, py = pin_pos(side.obj_type, side.pin_name, bitWidth=bw)
        node: int = (_new_pin    (na, bit_nodes, bits[0], side.node_is_output, 1,  rx=px, ry=py) if bw == 1
                else  _new_bus_pin(na, bit_nodes, bits,   side.node_is_output, bw, rx=px, ry=py))

        entry: CompDict = CompDict(
            x=side.x, y=port_y,
            objectType=side.obj_type, label=port_name,
            direction=side.cv_dir, labelDirection=side.label_dir,
            propagationDelay=0,
            customData=CVCustomData(
                constructorParamaters=[side.cv_dir, str(bw) if bw > 1 else 1,
                    {"x": side.layout_pin_x, "y": side.layout_pin_y, "id": f"p_{port_name}"}],
                nodes={side.pin_name: node},
                values={"state": 0} if direction == "input" else None,
            ),
        )

        side.cv_list.append(entry)
        _log.debug("place_ports: %s '%s' at (%d, %d) target=%s",
                   direction, port_name, side.x, port_y, target_cell)
        if direction == "input":
            layout_pin_y_in  += 20
        else:
            layout_pin_y_out += 20

    # Compute overall y extents for layout height calculation
    y_in: int = max((c.y + CELL_GAP for c in cv_inputs), default=0)
    y_out: int = max((c.y + CELL_GAP for c in cv_outputs), default=0)

    return cv_inputs, cv_outputs, cv_splitters, y_in, y_out
