"""Shared CircuitVerse helpers: node allocator, scope IDs, layout, scope builder,
and common component patterns (zero-extension, polarity inversion, constants)."""

import logging

from cv_utils import _extract_comp_params  # noqa: F401 — used by verify_routing + re-exported

_log = logging.getLogger(__name__)


class _CVNodeAlloc:
    """Allocate sequential node IDs for CircuitVerse allNodes list."""

    def __init__(self):
        self.nodes = []  # list of node dicts
        self.abs_pos = []  # (abs_x, abs_y) for each node

    def alloc(self, x, y, ntype, bit_width, label="", parent_id=None):
        nid = len(self.nodes)
        node = {
            "x": x, "y": y,
            "type": ntype,  # 0=input, 1=output, 2=bidir
            "bitWidth": bit_width,
            "label": label,
            "connections": [],
        }
        self.nodes.append(node)
        self.abs_pos.append((0, 0))  # set later via set_parent_pos
        return nid

    def set_parent_pos(self, nid, parent_x, parent_y, direction="RIGHT"):
        """Record the absolute position of a node (parent pos + relative).

        Pin coordinates are stored in RIGHT orientation.  For LEFT-direction
        components the x axis must be mirrored so that ``abs_pos`` reflects
        the *visual* position used by the router.
        """
        n = self.nodes[nid]
        nx = -n["x"] if direction == "LEFT" else n["x"]
        self.abs_pos[nid] = (parent_x + nx, parent_y + n["y"])

    def connect(self, a, b):
        if b not in self.nodes[a]["connections"]:
            self.nodes[a]["connections"].append(b)
        if a not in self.nodes[b]["connections"]:
            self.nodes[b]["connections"].append(a)

    def verify_routing(self, components=None):
        """Check for routing issues: diagonals, visual shorts, clearance, endpoints-on-wire.

        Prints warnings to stderr.  Returns number of issues found.
        """
        issues = 0
        GRID = 10

        # Build absolute positions (bend nodes already absolute)
        # Collect all wire segments per net (BFS from each connected component)
        visited = set()
        nets = []  # list of (set_of_nids, set_of_cells, set_of_segments)

        # Collect component pin node IDs so we can exclude them from endpoint checks
        comp_pin_nids = set()
        if components:
            for comp in components:
                cd = comp.get("customData", {}).get("nodes", {})
                for val in cd.values():
                    if isinstance(val, int):
                        comp_pin_nids.add(val)
                    elif isinstance(val, list):
                        for nid in val:
                            if isinstance(nid, int):
                                comp_pin_nids.add(nid)

        for start in range(len(self.nodes)):
            if start in visited or not self.nodes[start]["connections"]:
                continue
            net_nids = set()
            queue = [start]
            while queue:
                nid = queue.pop(0)
                if nid in net_nids:
                    continue
                net_nids.add(nid)
                for cid in self.nodes[nid]["connections"]:
                    if cid not in net_nids:
                        queue.append(cid)
            visited |= net_nids

            # Collect grid cells and segments occupied by this net
            net_cells = set()
            net_segments = set()  # ((x1,y1),(x2,y2)) normalized
            for nid in net_nids:
                ax, ay = self.abs_pos[nid]
                for cid in self.nodes[nid]["connections"]:
                    if cid > nid:
                        bx, by = self.abs_pos[cid]
                        if ax == bx:
                            for y in range(min(ay, by), max(ay, by) + GRID, GRID):
                                net_cells.add((ax, y))
                            net_segments.add(('V', ax, min(ay, by), max(ay, by)))
                        elif ay == by:
                            for x in range(min(ax, bx), max(ax, bx) + GRID, GRID):
                                net_cells.add((x, ay))
                            net_segments.add(('H', ay, min(ax, bx), max(ax, bx)))
                        else:
                            issues += 1
                            _log.warning("DIAG: node %d(%d,%d) <-> node %d(%d,%d)",
                                         nid, ax, ay, cid, bx, by)
            # Junction cells: nodes with 3+ connections (T or star junctions)
            junction_cells = set()
            for nid in net_nids:
                if len(self.nodes[nid]["connections"]) >= 3:
                    junction_cells.add(self.abs_pos[nid])
            nets.append((net_nids, net_cells, net_segments, junction_cells))

        # ── Check 1: visual shorts vs harmless crossings ──
        # SHORT: a junction (3+ connections) from one net sits on another net's cell
        # CROSS: two wires simply pass through the same cell (no junction → no connection)
        for i in range(len(nets)):
            for j in range(i + 1, len(nets)):
                shared = nets[i][1] & nets[j][1]
                if shared:
                    sample_i = min(nets[i][0])
                    sample_j = min(nets[j][0])
                    junctions = nets[i][3] | nets[j][3]
                    shorted = shared & junctions
                    crossed = shared - junctions
                    if shorted:
                        issues += len(shorted)
                        _log.warning("SHORT: nets (node %d...) and (node %d...) "
                                     "share %d junction cells, e.g. %s",
                                     sample_i, sample_j, len(shorted), sorted(shorted)[:3])
                    if crossed:
                        _log.info("CROSS: nets (node %d...) and (node %d...) "
                                  "cross at %d cells, e.g. %s",
                                  sample_i, sample_j, len(crossed), sorted(crossed)[:3])

        # ── Check 2: segment overlaps (collinear segments from different nets)
        for i in range(len(nets)):
            for j in range(i + 1, len(nets)):
                for seg_i in nets[i][2]:
                    for seg_j in nets[j][2]:
                        if seg_i[0] != seg_j[0]:
                            continue  # different orientation
                        if seg_i[1] != seg_j[1]:
                            continue  # different axis coordinate
                        # Same orientation & axis — check range overlap
                        if seg_i[2] < seg_j[3] and seg_j[2] < seg_i[3]:
                            shared_start = max(seg_i[2], seg_j[2])
                            shared_end = min(seg_i[3], seg_j[3])
                            issues += 1
                            sample_i = min(nets[i][0])
                            sample_j = min(nets[j][0])
                            _log.warning("OVERLAP: nets (node %d...) and (node %d...) "
                                         "%s at %s=%d range [%d,%d]",
                                         sample_i, sample_j, seg_i[0],
                                         'y' if seg_i[0] == 'H' else 'x',
                                         seg_i[1], shared_start, shared_end)

        # ── Check 3: wire endpoint lands on another net's segment
        for i, (nids_i, _, segs_i, _) in enumerate(nets):
            # Collect non-pin node positions (bend/wire nodes that are endpoints)
            for nid in nids_i:
                if nid in comp_pin_nids:
                    continue
                ax, ay = self.abs_pos[nid]
                for j, (_, _, segs_j, _) in enumerate(nets):
                    if i == j:
                        continue
                    for seg in segs_j:
                        if seg[0] == 'H' and ay == seg[1] and seg[2] < ax < seg[3]:
                            issues += 1
                            sample_j = min(nets[j][0])
                            _log.warning("ENDPOINT_ON_WIRE: node %d(%d,%d) "
                                         "lands on net (node %d...) "
                                         "H segment y=%d x=[%d,%d]",
                                         nid, ax, ay, sample_j, seg[1], seg[2], seg[3])
                        elif seg[0] == 'V' and ax == seg[1] and seg[2] < ay < seg[3]:
                            issues += 1
                            sample_j = min(nets[j][0])
                            _log.warning("ENDPOINT_ON_WIRE: node %d(%d,%d) "
                                         "lands on net (node %d...) "
                                         "V segment x=%d y=[%d,%d]",
                                         nid, ax, ay, sample_j, seg[1], seg[2], seg[3])

        # ── Check 4: wire segments crossing component bodies (clearance violation)
        if components:
            from circuitverse.components.registry import dimensions as _ref_dimensions
            for comp in components:
                cx, cy = comp.get("x", 0), comp.get("y", 0)
                ct = comp.get("objectType", "")
                if not ct:
                    continue
                params = _extract_comp_params(ct, comp)
                try:
                    dim = _ref_dimensions(ct, **params)
                except KeyError:
                    continue
                # Component body bounding box (exclusive of edge — pins sit on edge)
                bx0 = cx - dim["left"] + 1
                bx1 = cx + dim["right"] - 1
                by0 = cy - dim["up"] + 1
                by1 = cy + dim["down"] - 1

                # Collect this component's own pin nids
                own_nids = set()
                cd = comp.get("customData", {}).get("nodes", {})
                for val in cd.values():
                    if isinstance(val, int):
                        own_nids.add(val)
                    elif isinstance(val, list):
                        for nid in val:
                            if isinstance(nid, int):
                                own_nids.add(nid)

                # Pin abs positions for this component
                own_pin_pos = {self.abs_pos[nid] for nid in own_nids}

                for _, _, net_segs, _ in nets:
                    for seg in net_segs:
                        if seg[0] == 'H':
                            sy = seg[1]
                            sx0, sx1 = seg[2], seg[3]
                            if by0 <= sy <= by1 and sx0 < bx1 and sx1 > bx0:
                                # Allow if any pin of this component lies on the segment
                                if any(py == sy and sx0 <= px <= sx1 for px, py in own_pin_pos):
                                    continue
                                issues += 1
                                _log.warning("CLEARANCE: H wire y=%d x=[%d,%d] "
                                             "crosses %s@(%d,%d) body [%d,%d]x[%d,%d]",
                                             sy, sx0, sx1, ct, cx, cy,
                                             cx - dim['left'], cx + dim['right'],
                                             cy - dim['up'], cy + dim['down'])
                        elif seg[0] == 'V':
                            sx = seg[1]
                            sy0, sy1 = seg[2], seg[3]
                            if bx0 <= sx <= bx1 and sy0 < by1 and sy1 > by0:
                                # Allow if any pin of this component lies on the segment
                                if any(px == sx and sy0 <= py <= sy1 for px, py in own_pin_pos):
                                    continue
                                issues += 1
                                _log.warning("CLEARANCE: V wire x=%d y=[%d,%d] "
                                             "crosses %s@(%d,%d) body [%d,%d]x[%d,%d]",
                                             sx, sy0, sy1, ct, cx, cy,
                                             cx - dim['left'], cx + dim['right'],
                                             cy - dim['up'], cy + dim['down'])

        if issues == 0:
            _log.info("ROUTE OK: no issues found")
        else:
            _log.warning("ROUTE: %d issue(s) found", issues)
        return issues

    def route_orthogonal(self, components=None):
        """Insert intermediate type-2 nodes so all wires are orthogonal."""
        from cv_router import route_orthogonal as _route
        _route(self.nodes, self.abs_pos, components)


def _cv_scope_id():
    """Generate a unique scope ID for CircuitVerse."""
    _cv_scope_id._counter += 1
    return str(10000000000 + _cv_scope_id._counter)
_cv_scope_id._counter = -1


def _cv_layout(n_inputs, n_outputs):
    """Compute subcircuit layout block size."""
    n_max = max(n_inputs, n_outputs, 1)
    return {
        "width": 120,
        "height": 20 * n_max + 20,
        "title_x": 50,
        "title_y": 13,
        "titleEnabled": True,
    }


def _build_cv_scope(mod, na):
    """Build a CircuitVerse scope dict for a Module (subcircuit definition).

    Returns (scope_dict, scope_id, pin_positions).
    pin_positions maps port_name -> {"x": ..., "y": ...} for SubCircuit node
    placement in the parent.
    """
    scope_id = _cv_scope_id()
    sna = _CVNodeAlloc()
    layout = _cv_layout(len(mod.inputs), len(mod.outputs))
    layout_w = layout["width"]

    inputs = []
    outputs = []
    pin_positions = {}  # port_name -> {x, y} on the SubCircuit box

    pin_y = 20
    for p in mod.inputs:
        out_node = sna.alloc(10, 0, 1, p.width)
        bw = str(p.width) if p.width > 1 else 1
        pin_positions[p.name] = {"x": 0, "y": pin_y}
        inputs.append({
            "x": -20, "y": pin_y - 20,
            "objectType": "Input",
            "label": p.name,
            "direction": "RIGHT",
            "labelDirection": "LEFT",
            "propagationDelay": 0,
            "customData": {
                "nodes": {"output1": out_node},
                "values": {"state": 0},
                "constructorParamaters": [
                    "RIGHT", bw,
                    {"x": 0, "y": pin_y, "id": f"sc_{mod.name}_{p.name}"},
                ],
            },
        })
        pin_y += 20

    pin_y = 20
    for p in mod.outputs:
        inp_node = sna.alloc(-10, 0, 0, p.width)
        bw = str(p.width) if p.width > 1 else 1
        pin_positions[p.name] = {"x": layout_w, "y": pin_y}
        outputs.append({
            "x": layout_w + 20, "y": pin_y - 20,
            "objectType": "Output",
            "label": p.name,
            "direction": "LEFT",
            "labelDirection": "RIGHT",
            "propagationDelay": 0,
            "customData": {
                "nodes": {"inp1": inp_node},
                "constructorParamaters": [
                    "LEFT", bw,
                    {"x": layout_w, "y": pin_y, "id": f"sc_{mod.name}_{p.name}"},
                ],
            },
        })
        pin_y += 20

    scope = {
        "layout": layout,
        "verilogMetadata": {
            "isVerilogCircuit": False,
            "isMainCircuit": False,
            "code": "",
            "subCircuitScopeIds": [],
        },
        "allNodes": sna.nodes,
        "id": scope_id,
        "name": mod.name,
        "Input": inputs,
        "Output": outputs,
        "restrictedCircuitElementsUsed": [],
        "nodes": list(range(len(sna.nodes))),
    }
    return scope, scope_id, pin_positions


# ---------------------------------------------------------------------------
# Common component patterns used by high-level cell handlers
# ---------------------------------------------------------------------------

def emit_constant(na, bit_nodes, value_str, bw, x, y):
    """Emit a ConstantVal component.

    value_str: binary string like "00000001" (MSB first, length == bw).
    Returns (component_dict, output_node_id).
    """
    out_node = na.alloc(bw * 10, 0, 1, bw)
    comp = {
        "x": x, "y": y,
        "objectType": "ConstantVal",
        "label": "",
        "direction": "RIGHT",
        "labelDirection": "LEFT",
        "propagationDelay": 10,
        "customData": {
            "constructorParamaters": ["RIGHT", bw, value_str],
            "nodes": {"output1": out_node},
        },
    }
    return comp, out_node


def emit_not_gate(na, bit_nodes, bw, x, y):
    """Emit a NotGate component.

    Returns (component_dict, inp_node_id, out_node_id).
    """
    inp = na.alloc(-10, 0, 0, bw)
    out = na.alloc(20, 0, 1, bw)
    comp = {
        "x": x, "y": y,
        "objectType": "NotGate",
        "label": "",
        "direction": "RIGHT",
        "labelDirection": "LEFT",
        "propagationDelay": 100,
        "customData": {
            "constructorParamaters": ["RIGHT", bw],
            "nodes": {"inp1": inp, "output1": out},
        },
    }
    return comp, inp, out


def emit_zero_extend(na, bit_nodes, in_bw, out_bw, x, y):
    """Emit a Splitter + ConstantVal(0) to zero-extend a signal.

    Returns (components_list, input_node_id, output_node_id).
    Where input_node_id is the narrow input and output_node_id is the wide output.
    """
    extra = out_bw - in_bw
    comps = []

    # Splitter: groups = [in_bw, extra], direction LEFT (combining)
    spl_inp = na.alloc(20, (1) * 10, 1, out_bw)  # wide output
    spl_out0 = na.alloc(-10, -10 * 0, 0, in_bw)  # narrow input
    spl_out1 = na.alloc(-10, -10 * 0 + 20, 0, extra)  # zero padding
    comps.append({
        "x": x, "y": y,
        "objectType": "Splitter",
        "label": "",
        "direction": "LEFT",
        "labelDirection": "RIGHT",
        "propagationDelay": 10,
        "customData": {
            "constructorParamaters": ["LEFT", out_bw, [in_bw, extra]],
            "nodes": {"outputs": [spl_out0, spl_out1], "inp1": spl_inp},
        },
    })

    # ConstantVal: all zeros for the extra bits
    zero_str = "0" * extra
    zero_comp, zero_out = emit_constant(na, bit_nodes, zero_str, extra, x - 60, y + 20)
    comps.append(zero_comp)
    na.connect(zero_out, spl_out1)

    return comps, spl_out0, spl_inp


def register_bits(na, bit_nodes, bits, node_id, bw):
    """Register a multi-bit node on all its Yosys bit indices.

    For a multi-bit node, each bit index in the Yosys bits array maps to the
    same node_id. This only works when all bits belong to the same bus.
    """
    for b in bits:
        if not isinstance(b, str):
            bit_nodes.setdefault(b, []).append(node_id)


def unique_pos(x, y, used, step=20):
    """Nudge y until (x, y) is not in the used set, then register it."""
    while (x, y) in used:
        y += step
    used.add((x, y))
    return x, y


def emit_splitter(na, bw, groups, direction, x, y,
                  inp_node=None, out_nodes=None):
    """Emit a Splitter component.

    direction: "RIGHT" (fan-out / split) or "LEFT" (fan-in / join).
    groups: list of bit widths per output (e.g. [1, 1, 1] or [4, 2]).

    Returns (component_dict, inp_node, output_nodes_list).
    If inp_node/out_nodes are None, allocates with standard positions.
    """
    n = len(groups)
    if direction == "RIGHT":
        if inp_node is None:
            inp_node = na.alloc(-10, (bw - 1) * 10, 0, bw)
        if out_nodes is None:
            out_nodes = []
            for i, g in enumerate(groups):
                out_nodes.append(na.alloc(20, -10 * (n - 1) + i * 20, 1, g))
    else:
        if out_nodes is None:
            out_nodes = []
            for i, g in enumerate(groups):
                out_nodes.append(na.alloc(-10, -10 * (n - 1) + i * 20, 0, g))
        if inp_node is None:
            inp_node = na.alloc(20, (bw - 1) * 10, 1, bw)

    label_dir = "LEFT" if direction == "RIGHT" else "RIGHT"
    comp = {
        "x": x, "y": y,
        "objectType": "Splitter",
        "label": "",
        "direction": direction,
        "labelDirection": label_dir,
        "propagationDelay": 10,
        "customData": {
            "constructorParamaters": [direction, bw, groups],
            "nodes": {"outputs": out_nodes, "inp1": inp_node},
        },
    }
    return comp, inp_node, out_nodes


def emit_split_reduce(na, bit_nodes, components, bw, inp_node,
                      gate_type, spl_x, spl_y, gate_x, gate_y):
    """Split a multi-bit signal to 1-bit lines and reduce through an N-input gate.

    inp_node: the multi-bit source node (already allocated, already connected).
    gate_type: "AndGate", "OrGate", "NorGate", "XorGate", "XnorGate", "NandGate".

    Emits a Splitter + gate, appends both to components.
    Returns the 1-bit output node ID.
    """
    spl_comp, spl_inp, spl_outputs = emit_splitter(
        na, bw, [1] * bw, "RIGHT", spl_x, spl_y)
    na.connect(inp_node, spl_inp)
    components.setdefault("Splitter", []).append(spl_comp)

    from circuitverse.components.registry import pin_pos, gate_output_pos
    gate_inputs = []
    for i, spl_out in enumerate(spl_outputs):
        ix, iy = pin_pos(gate_type, "inp", index=i, inputLength=bw)
        gate_inp = na.alloc(ix, iy, 0, 1)
        na.connect(spl_out, gate_inp)
        gate_inputs.append(gate_inp)
    ox, oy = gate_output_pos(gate_type)
    gate_out = na.alloc(ox, oy, 1, 1)

    components.setdefault(gate_type, []).append({
        "x": gate_x, "y": gate_y,
        "objectType": gate_type,
        "label": "",
        "direction": "RIGHT",
        "labelDirection": "LEFT",
        "propagationDelay": 100,
        "customData": {
            "constructorParamaters": ["RIGHT", bw, 1],
            "nodes": {"inp": gate_inputs, "output1": gate_out},
        },
    })
    return gate_out


def emit_component(na, component_type, x, y, direction="RIGHT", label="",
                   propagation_delay=100, bitWidth=1, **extra_params):
    """Emit any simple component using the registry for pin positions.

    Handles components with static pins (fixed x/y in the reference).
    For components with dynamic/array pins (gates, mux), use specialized
    emitters or manual allocation.

    Returns (component_dict, {pin_name: node_id}).
    """
    from circuitverse.components.registry import _COMPONENTS, _resolve_bw, pin_pos

    comp_ref = _COMPONENTS.get(component_type)
    if comp_ref is None:
        raise KeyError(f"Unknown component: {component_type}")

    params = {"bitWidth": bitWidth, **extra_params}
    pin_nodes = {}
    nodes_dict = {}

    for pname, pinfo in comp_ref.get("pins", {}).items():
        # Skip array pins — caller must handle these
        if "count" in pinfo or "positions_formula" in pinfo:
            continue
        try:
            px, py = pin_pos(component_type, pname, **params)
        except KeyError:
            continue
        ptype = pinfo.get("type", "input")
        ntype = 0 if ptype == "input" else 1
        bw = _resolve_bw(pinfo.get("bitWidth", 1), params)
        nid = na.alloc(px, py, ntype, bw)
        pin_nodes[pname] = nid
        nodes_dict[pname] = nid

    # Build constructor params from reference
    ctor_params = [direction]
    for cp in comp_ref.get("constructor_params", []):
        cpname = cp["name"]
        if cpname == "direction":
            continue
        if cpname in params:
            ctor_params.append(params[cpname])
        elif "default" in cp and cp["default"] is not None:
            ctor_params.append(cp["default"])

    label_dir = {"RIGHT": "LEFT", "LEFT": "RIGHT",
                 "UP": "DOWN", "DOWN": "UP"}.get(direction, "LEFT")

    comp = {
        "x": x, "y": y,
        "objectType": component_type,
        "label": label,
        "direction": direction,
        "labelDirection": label_dir,
        "propagationDelay": propagation_delay,
        "customData": {
            "constructorParamaters": ctor_params,
            "nodes": nodes_dict,
        },
    }
    return comp, pin_nodes
