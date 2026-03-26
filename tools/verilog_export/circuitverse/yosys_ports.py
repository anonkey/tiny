"""Port placement for CircuitVerse: Input/Output with splitters.

Layout columns (left to right):
  x=0          Input components
  x=100        Input splitters (multi-bit → grouped)
  x=X_START    First gate column (depth 0)
  ...          More gate columns (depth 1, 2, ...)
  x=last+100   Output joiners (grouped → multi-bit)
  x=last+200   Output components

All positions snap to 10×10 grid.
"""

from circuitverse.components._common import _new_pin, _new_bus_pin, CELL_GAP, COL_GAP, X_START, pin_clearance
from circuitverse.components.registry import pin_pos, dimensions


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


def _compute_port_x(ymod, col_x, col_cells, max_in_groups=None, max_out_groups=None):
    """Compute x positions for Input, Splitter, Joiner, Output columns.

    Uses pin-count-based clearance between component body edges.
    max_in_groups/max_out_groups override splitter/joiner pin counts
    when split groups are wider than 1 bit.
    Returns (inp_x, spl_x, join_x, out_x).
    """
    # Find max input/output bitwidth to size IO bodies
    max_in_bw = 1
    max_out_bw = 1
    for port_name, port_info in ymod.get("ports", {}).items():
        bw = len(port_info["bits"])
        if port_info["direction"] == "input":
            max_in_bw = max(max_in_bw, bw)
        else:
            max_out_bw = max(max_out_bw, bw)

    # Gap 1: Input → Splitter
    # Input right: 1 pin (output1), Splitter left: 1 pin (inp1)
    inp_x = 0
    inp_right = inp_x + max_in_bw * 10  # Input body right edge
    spl_left_dim = 10  # Splitter left dimension
    gap_inp_spl = pin_clearance(1) + pin_clearance(1)  # 20 + 20 = 40
    spl_x = inp_right + gap_inp_spl + spl_left_dim
    spl_x = ((spl_x + 9) // 10) * 10  # snap to grid

    # Gap 2: Splitter → first cell column
    # Splitter right: one pin per split group (not per bit)
    spl_right = spl_x + 20  # Splitter body right + pin extent
    spl_right_pins = max_in_groups if max_in_groups is not None else max_in_bw
    if col_x:
        from circuitverse.yosys_layout import _col_extents
        extents = _col_extents(col_cells)
        first_depth = min(col_x.keys())
        first_left, _, first_left_pins, _ = extents.get(first_depth, (40, 40, 1, 1))
        first_col_x = col_x[first_depth]
        gap_spl_col = pin_clearance(spl_right_pins) + pin_clearance(first_left_pins)
        needed_start = spl_right + gap_spl_col + first_left
        needed_start = ((needed_start + 9) // 10) * 10
        if needed_start > first_col_x:
            shift = needed_start - first_col_x
            for d in col_x:
                col_x[d] += shift

    # Gap 3: last cell column → Joiner
    if col_x:
        last_depth = max(col_x.keys())
        _, last_right, _, last_right_pins = extents.get(last_depth, (40, 40, 1, 1))
        last_right_edge = col_x[last_depth] + last_right
    else:
        last_right_edge = X_START + 40
        last_right_pins = 1

    # Joiner (Splitter direction=LEFT): left side has one pin per group
    join_left_dim = 20
    join_left_pins = max_out_groups if max_out_groups is not None else max_out_bw
    gap_col_join = pin_clearance(last_right_pins) + pin_clearance(join_left_pins)
    join_x = last_right_edge + gap_col_join + join_left_dim
    join_x = ((join_x + 9) // 10) * 10

    # Gap 4: Joiner → Output
    # Joiner right: 1 pin (inp1), Output left: 1 pin (inp1)
    join_right = join_x + 20  # Splitter body right + pin extent
    out_left_dim = max_out_bw * 10
    gap_join_out = pin_clearance(1) + pin_clearance(1)  # 20 + 20 = 40
    out_x = join_right + gap_join_out + out_left_dim
    out_x = ((out_x + 9) // 10) * 10

    return inp_x, spl_x, join_x, out_x


def place_ports(ymod, na, bit_nodes, col_cells, col_x=None, layout_w=100):
    """Create Input/Output CV components with splitters for multi-bit ports.

    Returns (cv_inputs, cv_outputs, cv_splitters, y_in, y_out).
    """
    if col_x is None:
        col_x = {}

    # Pre-compute optimal split groups for all ports
    port_groups = {}
    max_in_groups = 1
    max_out_groups = 1
    for port_name, port_info in ymod.get("ports", {}).items():
        bits = port_info["bits"]
        bw = len(bits)
        if bw > 1:
            grps = _compute_split_groups(bits, port_info["direction"], ymod)
        else:
            grps = [1]
        port_groups[port_name] = grps
        if port_info["direction"] == "input":
            max_in_groups = max(max_in_groups, len(grps))
        else:
            max_out_groups = max(max_out_groups, len(grps))

    inp_x, spl_x, join_x, out_x = _compute_port_x(
        ymod, col_x, col_cells,
        max_in_groups=max_in_groups, max_out_groups=max_out_groups)

    cv_inputs = []
    cv_outputs = []
    cv_splitters = []
    y_in = 0
    y_out = 0
    layout_pin_y_in = 40
    layout_pin_y_out = 40

    for port_name, port_info in ymod.get("ports", {}).items():
        direction = port_info["direction"]
        bits = port_info["bits"]
        bw = len(bits)
        bws = port_groups[port_name]

        if direction == "input":
            inp_px, inp_py = pin_pos("Input", "output1", bitWidth=bw)
            if bw == 1:
                out_node = _new_pin(na, bit_nodes, bits[0], 1, 1, rx=inp_px, ry=inp_py)
            else:
                # Input component drives a bus node, split into groups
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
                    "x": spl_x, "y": y_in + 10,
                    "objectType": "Splitter",
                    "label": "",
                    "direction": "RIGHT",
                    "labelDirection": "LEFT",
                    "propagationDelay": 10,
                    "customData": {
                        "constructorParamaters": ["RIGHT", bw, bws],
                        "nodes": {
                            "outputs": spl_outputs,
                            "inp1": spl_inp,
                        },
                    },
                })

            cv_inputs.append({
                "x": inp_x, "y": y_in,
                "objectType": "Input",
                "label": port_name,
                "direction": "RIGHT",
                "labelDirection": "LEFT",
                "propagationDelay": 0,
                "customData": {
                    "nodes": {"output1": out_node},
                    "values": {"state": 0},
                    "constructorParamaters": ["RIGHT", str(bw) if bw > 1 else 1,
                        {"x": 0, "y": layout_pin_y_in, "id": f"p_{port_name}"}],
                },
            })
            y_in += max(bw * 20 + 20, CELL_GAP)
            layout_pin_y_in += 20

        else:
            out_px, out_py = pin_pos("Output", "inp1", bitWidth=bw)
            if bw == 1:
                inp_node = _new_pin(na, bit_nodes, bits[0], 0, 1, rx=out_px, ry=out_py)
            else:
                # Join grouped bits into bus for output
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
                    "x": join_x, "y": y_out + 10,
                    "objectType": "Splitter",
                    "label": "",
                    "direction": "LEFT",
                    "labelDirection": "RIGHT",
                    "propagationDelay": 10,
                    "customData": {
                        "constructorParamaters": ["LEFT", bw, bws],
                        "nodes": {
                            "outputs": jn_inputs,
                            "inp1": jn_out,
                        },
                    },
                })

            cv_outputs.append({
                "x": out_x, "y": y_out,
                "objectType": "Output",
                "label": port_name,
                "direction": "LEFT",
                "labelDirection": "RIGHT",
                "propagationDelay": 0,
                "customData": {
                    "nodes": {"inp1": inp_node},
                    "constructorParamaters": ["LEFT", str(bw) if bw > 1 else 1,
                        {"x": layout_w, "y": layout_pin_y_out, "id": f"p_{port_name}"}],
                },
            })
            y_out += max(bw * 20 + 20, CELL_GAP)
            layout_pin_y_out += 20

    return cv_inputs, cv_outputs, cv_splitters, y_in, y_out
