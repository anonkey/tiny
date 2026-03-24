"""Shared CircuitVerse helpers: node allocator, scope IDs, layout, scope builder,
and common component patterns (zero-extension, polarity inversion, constants)."""


def _extract_comp_params(comp_type, comp):
    """Extract dimension-relevant params from a component's constructorParamaters."""
    ctor = comp.get("customData", {}).get("constructorParamaters", [])
    params = {}
    if comp_type in ("Input", "Output", "ConstantVal"):
        if len(ctor) >= 2:
            bw = ctor[1]
            params["bitWidth"] = int(bw) if isinstance(bw, (int, str)) and str(bw).isdigit() else 1
    elif comp_type in ("Multiplexer", "Demultiplexer"):
        if len(ctor) >= 3 and not isinstance(ctor[2], list):
            params["controlSignalSize"] = int(ctor[2])
    elif comp_type == "Decoder":
        if len(ctor) >= 2:
            params["bitWidth"] = int(ctor[1]) if not isinstance(ctor[1], list) else 1
    elif comp_type == "Splitter":
        if len(ctor) >= 3 and isinstance(ctor[2], list):
            params["bitWidthSplit"] = ctor[2]
    elif comp_type in ("AndGate", "OrGate", "NandGate", "NorGate",
                        "XorGate", "XnorGate"):
        if len(ctor) >= 2:
            params["inputLength"] = int(ctor[1])
    return params


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
        import sys
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
                            print(f"ROUTE WARN DIAG: node {nid}({ax},{ay}) <-> node {cid}({bx},{by})",
                                  file=sys.stderr)
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
                        print(f"ROUTE WARN SHORT: nets (node {sample_i}...) and (node {sample_j}...) "
                              f"share {len(shorted)} junction cells, e.g. {sorted(shorted)[:3]}",
                              file=sys.stderr)
                    if crossed:
                        print(f"ROUTE INFO CROSS: nets (node {sample_i}...) and (node {sample_j}...) "
                              f"cross at {len(crossed)} cells, e.g. {sorted(crossed)[:3]}",
                              file=sys.stderr)

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
                            print(f"ROUTE WARN OVERLAP: nets (node {sample_i}...) and (node {sample_j}...) "
                                  f"{seg_i[0]} at {'y' if seg_i[0]=='H' else 'x'}={seg_i[1]} "
                                  f"range [{shared_start},{shared_end}]",
                                  file=sys.stderr)

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
                            print(f"ROUTE WARN ENDPOINT_ON_WIRE: node {nid}({ax},{ay}) "
                                  f"lands on net (node {sample_j}...) "
                                  f"H segment y={seg[1]} x=[{seg[2]},{seg[3]}]",
                                  file=sys.stderr)
                        elif seg[0] == 'V' and ax == seg[1] and seg[2] < ay < seg[3]:
                            issues += 1
                            sample_j = min(nets[j][0])
                            print(f"ROUTE WARN ENDPOINT_ON_WIRE: node {nid}({ax},{ay}) "
                                  f"lands on net (node {sample_j}...) "
                                  f"V segment x={seg[1]} y=[{seg[2]},{seg[3]}]",
                                  file=sys.stderr)

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
                                print(f"ROUTE WARN CLEARANCE: H wire y={sy} x=[{sx0},{sx1}] "
                                      f"crosses {ct}@({cx},{cy}) body "
                                      f"[{cx-dim['left']},{cx+dim['right']}]x"
                                      f"[{cy-dim['up']},{cy+dim['down']}]",
                                      file=sys.stderr)
                        elif seg[0] == 'V':
                            sx = seg[1]
                            sy0, sy1 = seg[2], seg[3]
                            if bx0 <= sx <= bx1 and sy0 < by1 and sy1 > by0:
                                # Allow if any pin of this component lies on the segment
                                if any(px == sx and sy0 <= py <= sy1 for px, py in own_pin_pos):
                                    continue
                                issues += 1
                                print(f"ROUTE WARN CLEARANCE: V wire x={sx} y=[{sy0},{sy1}] "
                                      f"crosses {ct}@({cx},{cy}) body "
                                      f"[{cx-dim['left']},{cx+dim['right']}]x"
                                      f"[{cy-dim['up']},{cy+dim['down']}]",
                                      file=sys.stderr)

        if issues == 0:
            print("ROUTE OK: no issues found", file=sys.stderr)
        else:
            print(f"ROUTE: {issues} issue(s) found", file=sys.stderr)
        return issues

    def route_orthogonal(self, components=None):
        """Insert intermediate type-2 nodes so all wires are orthogonal.

        Uses Left-Edge channel routing on a 2D occupancy grid.
        Component bounding boxes are marked as blocked so wires never
        pass through component bodies.
        """
        GRID = 10  # 1 grid cell = 10 deci-grid units
        PAD = 0    # no extra clearance — pins are at component edge

        num_original = len(self.nodes)

        def _snap(v):
            return round(v / GRID) * GRID

        def _make_bend(x, y, bw):
            x, y = _snap(x), _snap(y)
            nid = len(self.nodes)
            self.nodes.append({
                "x": x, "y": y,
                "type": 2,
                "bitWidth": bw,
                "label": "",
                "connections": [],
            })
            self.abs_pos.append((x, y))
            return nid

        def _disconnect(a, b):
            if b in self.nodes[a]["connections"]:
                self.nodes[a]["connections"].remove(b)
            if a in self.nodes[b]["connections"]:
                self.nodes[b]["connections"].remove(a)

        def _wire(a, b):
            if b not in self.nodes[a]["connections"]:
                self.nodes[a]["connections"].append(b)
            if a not in self.nodes[b]["connections"]:
                self.nodes[b]["connections"].append(a)

        # ── Phase 1: collect connection pairs ──
        pairs = set()
        for i in range(num_original):
            for j in self.nodes[i]["connections"]:
                if j < num_original:
                    pairs.add((min(i, j), max(i, j)))
        if not pairs:
            return

        # ── Phase 2: build nets via union-find ──
        parent = list(range(num_original))

        def _find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def _union(a, b):
            ra, rb = _find(a), _find(b)
            if ra != rb:
                parent[ra] = rb

        for a, b in pairs:
            _union(a, b)

        net_nodes = {}
        for a, b in pairs:
            root = _find(a)
            net_nodes.setdefault(root, set()).update([a, b])

        # ── Phase 3: characterize nets ──
        nets = []
        straight_nets = []  # (root, min_x, min_y, max_x, max_y) for wire_cells marking
        for root, node_ids in net_nodes.items():
            positions = [self.abs_pos[n] for n in node_ids]
            xs = [p[0] for p in positions]
            ys = [p[1] for p in positions]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            bw = self.nodes[next(iter(node_ids))]["bitWidth"]

            if min_x == max_x and min_y == max_y:
                continue
            if min_x == max_x or min_y == max_y:
                # Straight wire — no routing needed, but remember for wire_cells
                straight_nets.append((root, min_x, min_y, max_x, max_y))
                continue

            area = (max_x - min_x) * (max_y - min_y)
            nets.append({
                "root": root,
                "node_ids": node_ids,
                "min_x": min_x, "max_x": max_x,
                "min_y": min_y, "max_y": max_y,
                "bw": bw,
                "area": area,
            })

        if not nets:
            return

        # ── Phase 3b: precompute net interconnections ──
        # Two nets are interconnected if they share at least one abs position.
        net_positions = {}  # root -> set of (abs_x, abs_y)
        for root, node_ids in net_nodes.items():
            net_positions[root] = {self.abs_pos[n] for n in node_ids}

        pos_to_roots = {}  # (x, y) -> set of roots
        for root, positions in net_positions.items():
            for pos in positions:
                pos_to_roots.setdefault(pos, set()).add(root)

        connected_nets = {}  # root -> set of roots it's interconnected with
        for pos, roots in pos_to_roots.items():
            if len(roots) > 1:
                for r in roots:
                    connected_nets.setdefault(r, set()).update(roots - {r})

        # ── Phase 4: build occupancy grid ──
        orig_xs = [self.abs_pos[i][0] for i in range(num_original)]
        orig_ys = [self.abs_pos[i][1] for i in range(num_original)]
        # Grid: 1 cell = GRID deci-grid units. All abs_pos are in deci-grid.
        # Divide by GRID to get grid coords, multiply back when emitting bends.
        MARGIN = 30  # grid cells of margin around the layout
        min_gx = min(orig_xs) // GRID - MARGIN
        min_gy = min(orig_ys) // GRID - MARGIN
        max_gx = max(orig_xs) // GRID + MARGIN
        max_gy = max(orig_ys) // GRID + MARGIN
        gcols = max_gx - min_gx + 1
        grows = max_gy - min_gy + 1

        # Three cell states:
        # - hard_blocked: component body cells — NEVER unlockable
        # - soft_blocked: pin cells + their departure corridor — unlockable
        #   only when routing a net connected to that specific pin
        # - wire_cells: routed wire segments — crossable with heavy penalty
        hard_blocked = set()
        soft_blocked = {}  # (col, row) -> set of nids that can unlock it
        wire_cells = set()
        wire_dirs = {}  # (col, row) -> set of axes ('H' or 'V')
        wire_cell_owners = {}  # (col, row, axis) -> set of net root IDs

        # Mark straight-line nets in wire_cells so later nets avoid them
        for sn_root, sn_x0, sn_y0, sn_x1, sn_y1 in straight_nets:
            gc0, gr0 = sn_x0 // GRID - min_gx, sn_y0 // GRID - min_gy
            gc1, gr1 = sn_x1 // GRID - min_gx, sn_y1 // GRID - min_gy
            if gc0 == gc1:  # vertical
                for r in range(min(gr0, gr1), max(gr0, gr1) + 1):
                    wire_cells.add((gc0, r))
                    wire_dirs.setdefault((gc0, r), set()).add('V')
                    wire_cell_owners.setdefault((gc0, r, 'V'), set()).add(sn_root)
            else:  # horizontal
                for c in range(min(gc0, gc1), max(gc0, gc1) + 1):
                    wire_cells.add((c, gr0))
                    wire_dirs.setdefault((c, gr0), set()).add('H')
                    wire_cell_owners.setdefault((c, gr0, 'H'), set()).add(sn_root)

        CLEARANCE = 1

        # Build pin→component center map and populate blocking
        pin_depart = {}  # nid -> (dc, dr) departure direction
        pin_body = {}    # nid -> (bx0, bx1, by0, by1) in grid coords

        if components:
            from circuitverse.components.registry import dimensions as _ref_dimensions
            for comp in components:
                cx, cy = comp.get("x", 0), comp.get("y", 0)
                ct = comp.get("objectType", "")
                cd = comp.get("customData", {}).get("nodes", {})
                comp_nids = []
                for val in cd.values():
                    if isinstance(val, int) and val < num_original:
                        comp_nids.append(val)
                    elif isinstance(val, list):
                        for nid in val:
                            if isinstance(nid, int) and nid < num_original:
                                comp_nids.append(nid)
                if not comp_nids:
                    continue

                # Body size from reference dimensions
                if ct:
                    params = _extract_comp_params(ct, comp)
                    try:
                        dim = _ref_dimensions(ct, **params)
                    except KeyError:
                        dim = {"left": 20, "right": 20, "up": 20, "down": 20}
                else:
                    dim = {"left": 20, "right": 20, "up": 20, "down": 20}

                # Body bounding box in grid coords + CLEARANCE ring
                body_x0 = (cx - dim["left"]) // GRID - CLEARANCE
                body_x1 = (cx + dim["right"]) // GRID + CLEARANCE
                body_y0 = (cy - dim["up"]) // GRID - CLEARANCE
                body_y1 = (cy + dim["down"]) // GRID + CLEARANCE
                for gx in range(body_x0, body_x1 + 1):
                    for gy in range(body_y0, body_y1 + 1):
                        c = gx - min_gx
                        r = gy - min_gy
                        if 0 <= c < gcols and 0 <= r < grows:
                            hard_blocked.add((c, r))

                # Component center in grid coords (for departure direction)
                comp_gc = cx // GRID - min_gx
                comp_gr = cy // GRID - min_gy

                # Per-pin: compute departure direction + soft_blocked corridor
                import sys as _dbg
                for nid in comp_nids:
                    pc = self.abs_pos[nid][0] // GRID - min_gx
                    pr = self.abs_pos[nid][1] // GRID - min_gy
                    # Departure direction: pin beyond body edge → outward
                    # abs_pos already accounts for direction (visual coords)
                    rx = self.abs_pos[nid][0] - cx
                    ry = self.abs_pos[nid][1] - cy
                    if rx >= dim["right"]:
                        pin_depart[nid] = (1, 0)
                    elif rx <= -dim["left"]:
                        pin_depart[nid] = (-1, 0)
                    elif ry >= dim["down"]:
                        pin_depart[nid] = (0, 1)
                    elif ry <= -dim["up"]:
                        pin_depart[nid] = (0, -1)
                    else:
                        if abs(rx) >= abs(ry):
                            pin_depart[nid] = (1 if rx >= 0 else -1, 0)
                        else:
                            pin_depart[nid] = (0, 1 if ry >= 0 else -1)
                    dep_dc, dep_dr = pin_depart[nid]
                    _dbg.stderr.write(
                        f"DBG PIN nid={nid} abs={self.abs_pos[nid]} comp={ct}@({cx},{cy}) "
                        f"rx={rx} ry={ry} dim=l{dim['left']}r{dim['right']}u{dim['up']}d{dim['down']} "
                        f"depart={pin_depart[nid]}\n")

                    # Store body bounds for this pin (used by A* departure walk)
                    bx0 = body_x0 - min_gx
                    bx1 = body_x1 - min_gx
                    by0 = body_y0 - min_gy
                    by1 = body_y1 - min_gy
                    pin_body[nid] = (bx0, bx1, by0, by1)

                    # Pin cell itself → soft_blocked for this pin only
                    if 0 <= pc < gcols and 0 <= pr < grows:
                        soft_blocked.setdefault((pc, pr), set()).add(nid)
                    cc, cr = pc + dep_dc, pr + dep_dr
                    while (0 <= cc < gcols and 0 <= cr < grows
                           and bx0 <= cc <= bx1 and by0 <= cr <= by1):
                        soft_blocked.setdefault((cc, cr), set()).add(nid)
                        cc += dep_dc
                        cr += dep_dr
                    # One more cell outside for clearance
                    if 0 <= cc < gcols and 0 <= cr < grows:
                        soft_blocked.setdefault((cc, cr), set()).add(nid)

        # Build the effective blocked set: hard_blocked + all soft_blocked cells
        blocked = set(hard_blocked)
        for cell in soft_blocked:
            blocked.add(cell)

        import sys as _dbg
        _dbg.stderr.write(f"DBG grid={gcols}x{grows} min_gx={min_gx} min_gy={min_gy} hard={len(hard_blocked)} soft={len(soft_blocked)} total_blocked={len(blocked)}\n")
        _dbg.stderr.flush()

        def _col(x):
            """Convert deci-grid x to grid column."""
            return x // GRID - min_gx

        def _row(y):
            """Convert deci-grid y to grid row."""
            return y // GRID - min_gy

        def _to_world(c, r):
            """Convert grid (col, row) to deci-grid (x, y)."""
            return (c + min_gx) * GRID, (r + min_gy) * GRID

        # ── Phase 5: A* maze router (crossing = last resort) ──
        import heapq

        DC = [1, 0, -1, 0]
        DR = [0, 1, 0, -1]

        CROSS_PENALTY = 100  # heavy cost for crossing an existing wire

        def _astar_route(sc, sr, tc, tr):
            """A* shortest path.

            Wire cells may be crossed straight-through (perpendicular) but
            turning (bending) on a wire cell is forbidden — a bend creates a
            connection point in CircuitVerse, which would short two nets.
            """
            if sc == tc and sr == tr:
                return [(sc, sr)]

            # State: (col, row, direction)  direction = 0..3 or -1 (start)
            INF = float("inf")
            best = {}
            prev = {}
            pq = []
            g0 = 0
            h0 = abs(sc - tc) + abs(sr - tr)
            heapq.heappush(pq, (g0 + h0, g0, sc, sr, -1))
            best[(sc, sr, -1)] = g0

            while pq:
                f, g, c, r, d = heapq.heappop(pq)
                if g > best.get((c, r, d), INF):
                    continue
                if c == tc and r == tr:
                    # Reconstruct
                    path = [(c, r)]
                    state = (c, r, d)
                    while state in prev:
                        state = prev[state]
                        path.append((state[0], state[1]))
                    path.reverse()
                    # Extract waypoints (bend points only)
                    if len(path) <= 2:
                        return path
                    waypoints = [path[0]]
                    for i in range(1, len(path) - 1):
                        pc, pr = path[i - 1]
                        cc, cr = path[i]
                        nc, nr = path[i + 1]
                        if (nc - cc) != (cc - pc) or (nr - cr) != (cr - pr):
                            waypoints.append(path[i])
                    waypoints.append(path[-1])
                    return waypoints

                for i in range(4):
                    nc, nr = c + DC[i], r + DR[i]
                    if not (0 <= nc < gcols and 0 <= nr < grows):
                        continue
                    # Component body = impassable (unless it's the target pin)
                    if (nc, nr) in blocked and not (nc == tc and nr == tr):
                        continue
                    # Forbid turning on a wire cell (bend = connection point
                    # in CircuitVerse → creates unintended short)
                    # Allow if all wire owners at this cell are interconnected
                    is_turn = d != -1 and i != d
                    if is_turn and (c, r) in wire_cells:
                        all_owners = set()
                        for ax in wire_dirs.get((c, r), set()):
                            all_owners |= wire_cell_owners.get((c, r, ax), set())
                        current_root = net["root"]
                        my_connected = connected_nets.get(current_root, set())
                        if not all_owners.issubset(my_connected | {current_root}):
                            continue
                    # Forbid collinear movement along existing wire (overlap)
                    # unless current net is interconnected with the wire owner
                    step = 1
                    move_axis = 'H' if i in (0, 2) else 'V'
                    if (nc, nr) in wire_cells:
                        owners = wire_cell_owners.get((nc, nr, move_axis), set())
                        if owners:
                            current_root = net["root"]
                            my_connected = connected_nets.get(current_root, set())
                            if not owners.issubset(my_connected | {current_root}):
                                continue  # unrelated net — no overlap allowed
                        step += CROSS_PENALTY
                    ng = g + step
                    if ng < best.get((nc, nr, i), INF):
                        best[(nc, nr, i)] = ng
                        prev[(nc, nr, i)] = (c, r, d)
                        h = abs(nc - tc) + abs(nr - tr)
                        heapq.heappush(pq, (ng + h, ng, nc, nr, i))

            return None  # truly no path

        # Sort nets: smallest bounding box first (they block less)
        nets.sort(key=lambda n: n["area"])

        # ── Phase 6: route each net with A* ──
        for net_idx, net in enumerate(nets):
            import sys as _sys
            _sys.stderr.write(f"NET {net_idx}/{len(nets)} nodes={len(net['node_ids'])} bw={net['bw']}\n")
            _sys.stderr.flush()
            bw = net["bw"]
            node_ids = net["node_ids"]

            # Remove existing direct connections within this net
            existing_pairs = set()
            for nid in node_ids:
                for conn in list(self.nodes[nid]["connections"]):
                    if conn in node_ids:
                        existing_pairs.add((min(nid, conn), max(nid, conn)))
            for a, b in existing_pairs:
                _disconnect(a, b)

            # Decompose multi-pin net into 2-pin subnets (nearest-sink)
            nid_list = list(node_ids)
            routed_set = {nid_list[0]}  # start from first node
            remaining = set(nid_list[1:])
            # Collect all routed cells for this net (for blocking after)
            net_cells = set()

            def _pin_departure(nid):
                """Get the departure grid offset (dc, dr) for a pin.

                The wire leaves the pin 1 unit away from the component body.
                """
                if nid in pin_depart:
                    return pin_depart[nid]
                # Fallback for non-component nodes: output→right, input→left
                nt = self.nodes[nid]["type"]
                if nt == 1:
                    return (1, 0)
                elif nt == 0:
                    return (-1, 0)
                return (1, 0)

            while remaining:
                # Find nearest unrouted node to any routed node
                best_pair = None
                best_dist = float("inf")
                for src in routed_set:
                    sx, sy = self.abs_pos[src]
                    for dst in remaining:
                        dx, dy = self.abs_pos[dst]
                        dist = abs(sx - dx) + abs(sy - dy)
                        if dist < best_dist:
                            best_dist = dist
                            best_pair = (src, dst)

                src, dst = best_pair
                sx, sy = self.abs_pos[src]
                dx, dy = self.abs_pos[dst]

                sc, sr = _col(sx), _row(sy)
                tc, tr = _col(dx), _row(dy)

                # Same grid cell — just wire directly
                if sc == tc and sr == tr:
                    _wire(src, dst)
                    routed_set.add(dst)
                    remaining.discard(dst)
                    continue

                # Compute A* endpoints: walk from pin through own body only.
                src_dc, src_dr = _pin_departure(src)
                astar_sc, astar_sr = sc + src_dc, sr + src_dr
                if src in pin_body:
                    bx0, bx1, by0, by1 = pin_body[src]
                    while (bx0 <= astar_sc <= bx1 and by0 <= astar_sr <= by1):
                        astar_sc += src_dc
                        astar_sr += src_dr
                else:
                    while (astar_sc, astar_sr) in hard_blocked:
                        astar_sc += src_dc
                        astar_sr += src_dr

                # Nudge src departure off existing wires
                src_prenudge = None
                if (astar_sc, astar_sr) in wire_cells:
                    for pdc, pdr in [(src_dr, -src_dc), (-src_dr, src_dc)]:
                        nc, nr = astar_sc + pdc, astar_sr + pdr
                        if (nc, nr) not in wire_cells and (nc, nr) not in blocked:
                            src_prenudge = (astar_sc, astar_sr)
                            astar_sc, astar_sr = nc, nr
                            break

                dst_dc, dst_dr = _pin_departure(dst)
                astar_tc, astar_tr = tc + dst_dc, tr + dst_dr
                if dst in pin_body:
                    bx0, bx1, by0, by1 = pin_body[dst]
                    while (bx0 <= astar_tc <= bx1 and by0 <= astar_tr <= by1):
                        astar_tc += dst_dc
                        astar_tr += dst_dr
                else:
                    while (astar_tc, astar_tr) in hard_blocked:
                        astar_tc += dst_dc
                        astar_tr += dst_dr

                # Nudge dst departure off existing wires
                dst_prenudge = None
                if (astar_tc, astar_tr) in wire_cells:
                    for pdc, pdr in [(dst_dr, -dst_dc), (-dst_dr, dst_dc)]:
                        nc, nr = astar_tc + pdc, astar_tr + pdr
                        if (nc, nr) not in wire_cells and (nc, nr) not in blocked:
                            dst_prenudge = (astar_tc, astar_tr)
                            astar_tc, astar_tr = nc, nr
                            break

                # Unlock soft_blocked cells belonging to src and dst pins
                # (pin cells + their departure corridors)
                temp_unblocked = set()
                current_nids = {src, dst}
                for cell, nid_set in soft_blocked.items():
                    if current_nids & nid_set and cell in blocked:
                        blocked.discard(cell)
                        temp_unblocked.add(cell)

                # Unblock cells of already-routed segments of THIS net
                restored = set()
                for cell in net_cells:
                    if cell in blocked:
                        blocked.discard(cell)
                        restored.add(cell)

                # A* from departure to arrival
                _sys.stderr.write(
                    f"DBG ROUTE src={src} abs=({sx},{sy}) grid=({sc},{sr}) depart=({astar_sc},{astar_sr}) "
                    f"dst={dst} abs=({dx},{dy}) grid=({tc},{tr}) arrive=({astar_tc},{astar_tr})\n")
                path = _astar_route(astar_sc, astar_sr, astar_tc, astar_tr)
                if path:
                    _sys.stderr.write(f"DBG PATH: {' -> '.join(f'({c},{r})' for c,r in path)}\n")
                else:
                    _sys.stderr.write(f"DBG PATH: None (no path found)\n")

                # Restore all temporarily unblocked cells
                for cell in temp_unblocked:
                    blocked.add(cell)
                for cell in restored:
                    blocked.add(cell)

                if path is None:
                    import sys as _sys
                    _sys.stderr.write(
                        f"ROUTE FAIL: {src}({sx},{sy})->{dst}({dx},{dy}) "
                        f"depart({astar_sc},{astar_sr})->({astar_tc},{astar_tr}) "
                        f"grid={gcols}x{grows} blk={len(blocked)}\n"
                    )
                    _sys.stderr.flush()
                    _wire(src, dst)
                    routed_set.add(dst)
                    remaining.discard(dst)
                    continue

                # Wire: src_pin → [departure → A* path → arrival] → dst_pin
                # The path includes departure and arrival cells.
                # If src was nudged, insert a bend at the pre-nudge position
                # so the wire stays orthogonal: pin → pre-nudge → nudged.
                prev_nid = src
                if src_prenudge is not None:
                    wx, wy = _to_world(src_prenudge[0], src_prenudge[1])
                    bend = _make_bend(wx, wy, bw)
                    _wire(prev_nid, bend)
                    prev_nid = bend
                for i in range(len(path)):
                    wx, wy = _to_world(path[i][0], path[i][1])
                    bend = _make_bend(wx, wy, bw)
                    _wire(prev_nid, bend)
                    prev_nid = bend
                # If dst was nudged, insert a bend at the pre-nudge position
                # so the wire stays orthogonal: nudged → pre-nudge → pin.
                if dst_prenudge is not None:
                    wx, wy = _to_world(dst_prenudge[0], dst_prenudge[1])
                    bend = _make_bend(wx, wy, bw)
                    _wire(prev_nid, bend)
                    prev_nid = bend
                _wire(prev_nid, dst)

                # Mark routed wire cells (including pre-nudge segments)
                src_pre = [src_prenudge] if src_prenudge else []
                dst_pre = [dst_prenudge] if dst_prenudge else []
                full_path = [(sc, sr)] + src_pre + list(path) + dst_pre + [(tc, tr)]
                for i in range(len(full_path) - 1):
                    c0, r0 = full_path[i]
                    c1, r1 = full_path[i + 1]
                    net_root = net["root"]
                    if c0 == c1:
                        for r in range(min(r0, r1), max(r0, r1) + 1):
                            net_cells.add((c0, r))
                            wire_cells.add((c0, r))
                            wire_dirs.setdefault((c0, r), set()).add('V')
                            wire_cell_owners.setdefault((c0, r, 'V'), set()).add(net_root)
                    elif r0 == r1:
                        for c in range(min(c0, c1), max(c0, c1) + 1):
                            net_cells.add((c, r0))
                            wire_cells.add((c, r0))
                            wire_dirs.setdefault((c, r0), set()).add('H')
                            wire_cell_owners.setdefault((c, r0, 'H'), set()).add(net_root)

                routed_set.add(dst)
                remaining.discard(dst)


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
