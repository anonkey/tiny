"""Port placement for CircuitVerse: Input/Output with splitters.

Layout columns (left to right):
  x=0          Input components
  x=100        Input splitters (multi-bit → 1-bit)
  x=X_START    First gate column (depth 0)
  ...          More gate columns (depth 1, 2, ...)
  x=last+100   Output joiners (1-bit → multi-bit)
  x=last+200   Output components

All positions snap to 10×10 grid.
"""

from circuitverse.components._common import _new_pin, _new_bus_pin, CELL_GAP, COL_GAP, X_START, pin_clearance
from circuitverse.components.registry import pin_pos, dimensions


def _compute_port_x(ymod, col_x, col_cells):
    """Compute x positions for Input, Splitter, Joiner, Output columns.

    Uses pin-count-based clearance between component body edges.
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
    # Splitter right: max_in_bw pins (one per split bit)
    spl_right = spl_x + 20  # Splitter body right + pin extent
    spl_right_pins = max_in_bw
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

    # Joiner (Splitter direction=LEFT): left side has max_out_bw pins (one per bit)
    join_left_dim = 20
    join_left_pins = max_out_bw
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


def place_ports(ymod, na, bit_nodes, col_cells, col_x=None):
    """Create Input/Output CV components with splitters for multi-bit ports.

    Returns (cv_inputs, cv_outputs, cv_splitters, y_in, y_out).
    """
    if col_x is None:
        col_x = {}
    inp_x, spl_x, join_x, out_x = _compute_port_x(ymod, col_x, col_cells)

    cv_inputs = []
    cv_outputs = []
    cv_splitters = []
    y_in = 0
    y_out = 0

    for port_name, port_info in ymod.get("ports", {}).items():
        direction = port_info["direction"]
        bits = port_info["bits"]
        bw = len(bits)

        if direction == "input":
            inp_px, inp_py = pin_pos("Input", "output1", bitWidth=bw)
            if bw == 1:
                out_node = _new_pin(na, bit_nodes, bits[0], 1, 1, rx=inp_px, ry=inp_py)
            else:
                # Input component drives a bus node, split to individual bits
                out_node = na.alloc(inp_px, inp_py, 1, bw)
                bws = [1] * bw
                si_x, si_y = pin_pos("Splitter", "inp1", bitWidth=bw, bitWidthSplit=bws)
                spl_inp = na.alloc(si_x, si_y, 0, bw)
                na.connect(out_node, spl_inp)
                spl_outputs = []
                for i, b in enumerate(bits):
                    so_x, so_y = pin_pos("Splitter", "outputs", index=i, bitWidth=bw, bitWidthSplit=bws)
                    spl_out = _new_pin(na, bit_nodes, b, 1, 1, rx=so_x, ry=so_y)
                    spl_outputs.append(spl_out)
                cv_splitters.append({
                    "x": spl_x, "y": y_in + 10,
                    "objectType": "Splitter",
                    "label": "",
                    "direction": "RIGHT",
                    "labelDirection": "LEFT",
                    "propagationDelay": 10,
                    "customData": {
                        "constructorParamaters": ["RIGHT", bw, [1] * bw],
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
                        {"x": 0, "y": 20, "id": f"p_{port_name}"}],
                },
            })
            y_in += max(bw * 20 + 20, CELL_GAP)

        else:
            out_px, out_py = pin_pos("Output", "inp1", bitWidth=bw)
            if bw == 1:
                inp_node = _new_pin(na, bit_nodes, bits[0], 0, 1, rx=out_px, ry=out_py)
            else:
                # Join individual bits into bus for output
                inp_node = na.alloc(out_px, out_py, 0, bw)
                bws = [1] * bw
                ji_x, ji_y = pin_pos("Splitter", "inp1", bitWidth=bw, bitWidthSplit=bws)
                jn_out = na.alloc(ji_x, ji_y, 1, bw)
                na.connect(jn_out, inp_node)
                jn_inputs = []
                for i, b in enumerate(bits):
                    so_x, so_y = pin_pos("Splitter", "outputs", index=i, bitWidth=bw, bitWidthSplit=bws)
                    jn_in = _new_pin(na, bit_nodes, b, 0, 1, rx=so_x, ry=so_y)
                    jn_inputs.append(jn_in)
                cv_splitters.append({
                    "x": join_x, "y": y_out + 10,
                    "objectType": "Splitter",
                    "label": "",
                    "direction": "LEFT",
                    "labelDirection": "RIGHT",
                    "propagationDelay": 10,
                    "customData": {
                        "constructorParamaters": ["LEFT", bw, [1] * bw],
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
                        {"x": 0, "y": 20, "id": f"p_{port_name}"}],
                },
            })
            y_out += max(bw * 20 + 20, CELL_GAP)

    return cv_inputs, cv_outputs, cv_splitters, y_in, y_out
