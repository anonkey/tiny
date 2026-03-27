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

import logging

_log = logging.getLogger(__name__)

from common.constants import _new_pin, _new_bus_pin, CELL_GAP, COL_GAP, X_START, pin_clearance, CTOR_PARAMS_KEY, GRID_UNIT
from synthesis.gates.registry import pin_pos, dimensions


def _find_port_target(port_bits, direction, ymod, cell_depth):
    """Find the target cell for proximity placement.

    For inputs: returns cell_name of leftmost (min depth) consumer.
    For outputs: returns cell_name of rightmost (max depth) producer.
    Returns None if no connected cell found.
    """
    cells = ymod.get("cells", {})
    port_bits_set = set(b for b in port_bits if not isinstance(b, str))
    if not port_bits_set:
        return None

    target_dir = "input" if direction == "input" else "output"
    best_cell = None
    best_depth = None

    for cell_name, cell in cells.items():
        if cell.get("type") == "$scopeinfo":
            continue
        if cell_name not in cell_depth:
            continue
        dirs = cell.get("port_directions", {})
        conns = cell.get("connections", {})
        for pname, d in dirs.items():
            if d != target_dir:
                continue
            for b in conns.get(pname, []):
                if isinstance(b, str) or b not in port_bits_set:
                    continue
                d_val = cell_depth[cell_name]
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


def _snap(x):
    """Snap x to 10-unit grid (round up)."""
    return ((x + GRID_UNIT - 1) // GRID_UNIT) * GRID_UNIT


def compute_bbox(col_cells, col_x, cell_positions, sc_comps,
                 sub_scope_ids=None):
    """Compute bounding box of all placed non-port components.

    Returns (left, top, right, bottom) with padding for routing clearance.
    """
    from placement.layout import _col_extents
    if not col_x:
        # No cells — return a default box
        return (X_START, 0, X_START + 100, 100)

    extents = _col_extents(col_cells, sub_scope_ids)

    # Horizontal bounds from column extents
    left = min(col_x[d] - extents[d][0] for d in col_x)
    right = max(col_x[d] + extents[d][1] for d in col_x)

    # Vertical bounds from cell positions + estimated heights
    top = 0
    bottom = 0
    for cell_name, (cx, cy) in cell_positions.items():
        bottom = max(bottom, cy + CELL_GAP)  # conservative height estimate

    # Also account for subcircuit body extents
    for sc in sc_comps:
        sx, sy = sc["x"], sc["y"]
        dims = sc["customData"].get("_sc_dimensions", {})
        sc_right = sx + dims.get("right", 100)
        sc_bottom = sy + dims.get("down", 60)
        right = max(right, sc_right)
        bottom = max(bottom, sc_bottom)

    # Add padding so ports don't sit flush against cells
    pad = pin_clearance(2)
    _log.debug("compute_bbox: raw=(%d, %d, %d, %d) pad=%d",
               left, top, right, bottom, pad)
    return (left - pad, top, right + pad, bottom)


def place_ports(ymod, na, bit_nodes, col_cells, col_x=None,
                cell_depth=None, cell_positions=None, bbox=None,
                layout_w=100):
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

    bbox_left, bbox_top, bbox_right, bbox_bottom = bbox

    # Find max bitwidths for body/clearance sizing
    max_in_bw = max((len(p["bits"]) for p in ymod.get("ports", {}).values()
                     if p["direction"] == "input"), default=1)
    max_out_bw = max((len(p["bits"]) for p in ymod.get("ports", {}).values()
                     if p["direction"] == "output"), default=1)
    # Compute fixed x columns for inputs (left of bbox) and outputs (right of bbox)
    inp_body_right = max_in_bw * 10  # Input body right edge (from pin_pos formula)
    inp_clearance = max_in_bw * 20 + 20

    inp_x = _snap(bbox_left - inp_clearance - inp_body_right)

    out_body_left = max_out_bw * 10
    out_clearance = max_out_bw * 20 + 20

    out_x = _snap(bbox_right + out_clearance + out_body_left)

    _log.debug("place_ports: bbox=(%d,%d,%d,%d) inp_x=%d out_x=%d",
               bbox_left, bbox_top, bbox_right, bbox_bottom,
               inp_x, out_x)

    cv_inputs = []
    cv_outputs = []
    cv_splitters = []
    # Track used y-ranges per side to avoid overlaps
    # Each entry is (y_start, y_end)
    used_left = []
    used_right = []
    layout_pin_y_in = 40
    layout_pin_y_out = 40

    def _find_free_y(desired_y, height, used_ranges):
        """Find the nearest free y position starting from desired_y."""
        y = _snap(desired_y)
        # Sort ranges by start
        ranges = sorted(used_ranges)
        for ys, ye in ranges:
            if y + height <= ys or y >= ye:
                continue  # no overlap
            # Overlap — push below this range
            y = _snap(ye)
        return y

    for port_name, port_info in ymod.get("ports", {}).items():
        direction = port_info["direction"]
        bits = port_info["bits"]
        bw = len(bits)
        port_height = max(bw * 20 + 20, CELL_GAP)

        # Find target cell for proximity placement
        target_cell = _find_port_target(bits, direction, ymod, cell_depth)

        if direction == "input":
            # Compute y position — align with target cell, avoid overlaps
            if target_cell and target_cell in cell_positions:
                _, desired_y = cell_positions[target_cell]
            else:
                desired_y = used_left[-1][1] if used_left else 0
            port_y = _find_free_y(desired_y, port_height, used_left)
            used_left.append((port_y, port_y + port_height))

            inp_px, inp_py = pin_pos("Input", "output1", bitWidth=bw)
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

            out_px, out_py = pin_pos("Output", "inp1", bitWidth=bw)
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
    y_in = max((c["y"] + CELL_GAP for c in cv_inputs), default=0)
    y_out = max((c["y"] + CELL_GAP for c in cv_outputs), default=0)

    return cv_inputs, cv_outputs, cv_splitters, y_in, y_out
