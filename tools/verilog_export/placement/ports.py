"""Port placement for CircuitVerse: Input/Output with splitters.

Ports are placed **outside** the bounding box of all logic cells:
  - Inputs + splitters to the left of the bbox
  - Outputs + joiners to the right of the bbox
Each port aligns vertically with its target cell (leftmost consumer
for inputs, rightmost producer for outputs).

All positions snap to 10×10 grid.
"""

import logging

_log = logging.getLogger(__name__)

from common.constants import _new_pin, _new_bus_pin, CELL_GAP, COL_GAP, X_START, pin_clearance, CTOR_PARAMS_KEY, GRID_UNIT
from synthesis.gates.registry import pin_pos, dimensions


def _compute_split_groups(port_bits, direction, ymod):
    """Compute optimal bitWidthSplit groups for a port based on consumer/producer analysis.

    For 'input' ports: analyze which cells consume each bit.
    For 'output' ports: analyze which cells produce each bit.

    Consecutive bits consumed/produced by the same cell port at contiguous
    positions are grouped together.  E.g. a 4-bit port consumed as two
    2-bit buses returns [2, 2] instead of [1, 1, 1, 1].
    """
    cells = ymod.get("cells", {})
    bw = len(port_bits)
    if bw <= 1:
        return [1]

    target_dir = "input" if direction == "input" else "output"
    port_bits_set = set(b for b in port_bits if not isinstance(b, str))

    # For each bit index, collect (cell_name, port_name, position_in_port) refs
    bit_to_refs = {}
    for cell_name, cell in cells.items():
        if cell.get("type") == "$scopeinfo":
            continue
        dirs = cell.get("port_directions", {})
        conns = cell.get("connections", {})
        for pname, d in dirs.items():
            if d != target_dir:
                continue
            port_conn_bits = conns.get(pname, [])
            for pos, b in enumerate(port_conn_bits):
                if isinstance(b, str) or b not in port_bits_set:
                    continue
                bit_to_refs.setdefault(b, []).append((cell_name, pname, pos))

    # Sort each bit's refs for deterministic comparison
    for b in bit_to_refs:
        bit_to_refs[b] = sorted(bit_to_refs[b], key=lambda r: (r[0], r[1], r[2]))

    # Greedy left-to-right grouping
    groups = []
    i = 0
    while i < bw:
        bit = port_bits[i]
        if isinstance(bit, str):
            groups.append(1)
            i += 1
            continue

        refs = bit_to_refs.get(bit, [])
        if not refs:
            groups.append(1)
            i += 1
            continue

        group_len = 1
        while i + group_len < bw:
            next_bit = port_bits[i + group_len]
            if isinstance(next_bit, str):
                break
            next_refs = bit_to_refs.get(next_bit, [])
            if len(next_refs) != len(refs):
                break

            compatible = True
            for ref, next_ref in zip(refs, next_refs):
                if ref[0] != next_ref[0] or ref[1] != next_ref[1]:
                    compatible = False
                    break
                if next_ref[2] != ref[2] + group_len:
                    compatible = False
                    break
            if not compatible:
                break
            group_len += 1

        groups.append(group_len)
        i += group_len

    return groups


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

    # Pre-compute optimal split groups for all ports
    port_groups = {}
    for port_name, port_info in ymod.get("ports", {}).items():
        bits = port_info["bits"]
        bw = len(bits)
        if bw > 1:
            grps = _compute_split_groups(bits, port_info["direction"], ymod)
        else:
            grps = [1]
        port_groups[port_name] = grps

    # Find max bitwidths for body sizing
    max_in_bw = max((len(p["bits"]) for p in ymod.get("ports", {}).values()
                     if p["direction"] == "input"), default=1)
    max_out_bw = max((len(p["bits"]) for p in ymod.get("ports", {}).values()
                     if p["direction"] == "output"), default=1)

    # Compute fixed x columns for inputs (left of bbox) and outputs (right of bbox)
    inp_body_right = max_in_bw * 10  # Input body right edge (from pin_pos formula)
    inp_clearance = pin_clearance(1) + pin_clearance(1)  # 40
    spl_body_width = 30  # splitter left(10) + right(20)

    inp_x = _snap(bbox_left - inp_clearance - spl_body_width - inp_clearance - inp_body_right)
    spl_x = _snap((inp_x + inp_body_right + bbox_left) // 2)

    out_body_left = max_out_bw * 10
    out_clearance = pin_clearance(1) + pin_clearance(1)  # 40
    join_body_width = 30

    out_x = _snap(bbox_right + out_clearance + join_body_width + out_clearance + out_body_left)
    join_x = _snap((bbox_right + out_x - out_body_left) // 2)

    _log.debug("place_ports: bbox=(%d,%d,%d,%d) inp_x=%d spl_x=%d join_x=%d out_x=%d",
               bbox_left, bbox_top, bbox_right, bbox_bottom,
               inp_x, spl_x, join_x, out_x)

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
        bws = port_groups[port_name]
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
                out_node = na.alloc(inp_px, inp_py, 1, bw)
                si_x, si_y = pin_pos("Splitter", "inp1", bitWidth=bw, bitWidthSplit=bws)
                spl_inp = na.alloc(si_x, si_y, 0, bw)
                na.connect(out_node, spl_inp)
                spl_outputs = []
                bit_offset = 0
                for gi, gw in enumerate(bws):
                    so_x, so_y = pin_pos("Splitter", "outputs", index=gi, bitWidth=bw, bitWidthSplit=bws)
                    group_bits = bits[bit_offset:bit_offset + gw]
                    if gw == 1:
                        spl_out = _new_pin(na, bit_nodes, group_bits[0], 1, 1, rx=so_x, ry=so_y)
                    else:
                        spl_out = _new_bus_pin(na, bit_nodes, group_bits, 1, gw, rx=so_x, ry=so_y)
                    spl_outputs.append(spl_out)
                    bit_offset += gw
                cv_splitters.append({
                    "x": spl_x, "y": port_y + 10,
                    "objectType": "Splitter",
                    "label": "",
                    "direction": "RIGHT",
                    "labelDirection": "LEFT",
                    "propagationDelay": 10,
                    "customData": {
                        CTOR_PARAMS_KEY: ["RIGHT", bw, bws],
                        "nodes": {
                            "outputs": spl_outputs,
                            "inp1": spl_inp,
                        },
                    },
                })

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
                inp_node = na.alloc(out_px, out_py, 0, bw)
                ji_x, ji_y = pin_pos("Splitter", "inp1", bitWidth=bw, bitWidthSplit=bws)
                jn_out = na.alloc(ji_x, ji_y, 1, bw)
                na.connect(jn_out, inp_node)
                jn_inputs = []
                bit_offset = 0
                for gi, gw in enumerate(bws):
                    so_x, so_y = pin_pos("Splitter", "outputs", index=gi, bitWidth=bw, bitWidthSplit=bws)
                    group_bits = bits[bit_offset:bit_offset + gw]
                    if gw == 1:
                        jn_in = _new_pin(na, bit_nodes, group_bits[0], 0, 1, rx=so_x, ry=so_y)
                    else:
                        jn_in = _new_bus_pin(na, bit_nodes, group_bits, 0, gw, rx=so_x, ry=so_y)
                    jn_inputs.append(jn_in)
                    bit_offset += gw
                cv_splitters.append({
                    "x": join_x, "y": port_y + 10,
                    "objectType": "Splitter",
                    "label": "",
                    "direction": "LEFT",
                    "labelDirection": "RIGHT",
                    "propagationDelay": 10,
                    "customData": {
                        CTOR_PARAMS_KEY: ["LEFT", bw, bws],
                        "nodes": {
                            "outputs": jn_inputs,
                            "inp1": jn_out,
                        },
                    },
                })

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
    all_y = [c["y"] for c in cv_inputs + cv_outputs]
    y_in = max((c["y"] + CELL_GAP for c in cv_inputs), default=0)
    y_out = max((c["y"] + CELL_GAP for c in cv_outputs), default=0)

    return cv_inputs, cv_outputs, cv_splitters, y_in, y_out
