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

from components._common import _new_pin, _new_bus_pin, CELL_GAP, COL_GAP, X_START

# Columns for I/O
_INP_X = 0       # Input component
_SPL_X = 100     # Input splitter


def place_ports(ymod, na, bit_nodes, col_cells):
    """Create Input/Output CV components with splitters for multi-bit ports.

    Returns (cv_inputs, cv_outputs, cv_splitters, y_in, y_out).
    """
    cv_inputs = []
    cv_outputs = []
    cv_splitters = []
    max_depth = max(col_cells.keys()) if col_cells else 0
    y_in = 0
    y_out = 0

    for port_name, port_info in ymod.get("ports", {}).items():
        direction = port_info["direction"]
        bits = port_info["bits"]
        bw = len(bits)

        if direction == "input":
            if bw == 1:
                out_node = _new_pin(na, bit_nodes, bits[0], 1, 1, rx=10, ry=0)
            else:
                # Input component drives a bus node, split to individual bits
                out_node = na.alloc(10, 0, 1, bw)
                spl_inp = na.alloc(-10, (bw - 1) * 10, 0, bw)
                na.connect(out_node, spl_inp)
                spl_outputs = []
                for i, b in enumerate(bits):
                    spl_out = _new_pin(na, bit_nodes, b, 1, 1,
                                       rx=20, ry=-10 * (bw - 1) + i * 20)
                    spl_outputs.append(spl_out)
                cv_splitters.append({
                    "x": _SPL_X, "y": y_in + 10,
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
                "x": _INP_X, "y": y_in,
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
            out_x = X_START + (max_depth + 1) * COL_GAP
            join_x = out_x - 100

            if bw == 1:
                inp_node = _new_pin(na, bit_nodes, bits[0], 0, 1, rx=-10, ry=0)
            else:
                # Join individual bits into bus for output
                inp_node = na.alloc(-10, 0, 0, bw)
                jn_out = na.alloc(20, (bw - 1) * 10, 1, bw)
                na.connect(jn_out, inp_node)
                jn_inputs = []
                for i, b in enumerate(bits):
                    jn_in = _new_pin(na, bit_nodes, b, 0, 1,
                                     rx=-10, ry=-10 * (bw - 1) + i * 20)
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
