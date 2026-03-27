"""Orthogonal wire router for CircuitVerse export.

Extracts connection pairs, builds nets via union-find, constructs an
occupancy grid over component bodies, and routes each net with A*
maze routing + nearest-sink decomposition.
"""
from __future__ import annotations

import heapq
import logging
from collections.abc import Callable
from typing import Any

from common.constants import GRID_UNIT
from common.types import NodeDict, AbsPos, CompDict
from common.utils import _extract_comp_params

_log: logging.Logger = logging.getLogger(__name__)

# Direction offsets: right, down, left, up
_DC: list[int] = [1, 0, -1, 0]
_DR: list[int] = [0, 1, 0, -1]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _snap(v: int, grid: int = GRID_UNIT) -> int:
    return round(v / grid) * grid


def _same_axis(dc1: int, dr1: int, dc2: int, dr2: int) -> bool:
    """True if two direction vectors share the same axis (both H or both V)."""
    return (dc1 != 0) == (dc2 != 0) and (dr1 != 0) == (dr2 != 0)


def _make_bend(nodes: list[NodeDict], abs_pos: AbsPos, x: int, y: int, bw: int, grid: int = GRID_UNIT) -> int:
    """Create a type-2 bend node.  Returns the new node ID."""
    x, y = _snap(x, grid), _snap(y, grid)
    nid: int = len(nodes)
    nodes.append({
        "x": x, "y": y,
        "type": 2,
        "bitWidth": bw,
        "label": "",
        "connections": [],
    })
    abs_pos.append((x, y))
    return nid


def _disconnect(nodes: list[NodeDict], a: int, b: int) -> None:
    """Remove the edge between nodes *a* and *b*."""
    if b in nodes[a]["connections"]:
        nodes[a]["connections"].remove(b)
    if a in nodes[b]["connections"]:
        nodes[b]["connections"].remove(a)


def _wire(nodes: list[NodeDict], a: int, b: int) -> None:
    """Add an edge between nodes *a* and *b*."""
    if b not in nodes[a]["connections"]:
        nodes[a]["connections"].append(b)
    if a not in nodes[b]["connections"]:
        nodes[b]["connections"].append(a)


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------

class _UnionFind:
    """Disjoint-set with path compression."""

    _parent: list[int]

    def __init__(self, n: int) -> None:
        self._parent = list(range(n))

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------

def _collect_pairs(nodes: list[NodeDict], num_original: int) -> set[tuple[int, int]]:
    """Phase 1: collect unique connection pairs among original nodes."""
    pairs: set[tuple[int, int]] = set()
    for i in range(num_original):
        for j in nodes[i]["connections"]:
            if j < num_original:
                pairs.add((min(i, j), max(i, j)))
    return pairs


def _characterize_nets(net_nodes: dict[int, set[int]], nodes: list[NodeDict], abs_pos: AbsPos) -> tuple[list[dict[str, Any]], list[tuple[int, int, int, int, int]]]:
    """Phase 3: classify nets as point / straight / needs-routing.

    Returns (nets_to_route, straight_nets).
    """
    nets: list[dict[str, Any]] = []
    straight_nets: list[tuple[int, int, int, int, int]] = []
    for root, node_ids in net_nodes.items():
        positions: list[tuple[int, int]] = [abs_pos[n] for n in node_ids]
        xs: list[int] = [p[0] for p in positions]
        ys: list[int] = [p[1] for p in positions]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        bw: int = nodes[next(iter(node_ids))]["bitWidth"]

        if min_x == max_x and min_y == max_y:
            continue
        if min_x == max_x or min_y == max_y:
            straight_nets.append((root, min_x, min_y, max_x, max_y))
            continue

        area: int = (max_x - min_x) * (max_y - min_y)
        nets.append({
            "root": root,
            "node_ids": node_ids,
            "min_x": min_x, "max_x": max_x,
            "min_y": min_y, "max_y": max_y,
            "bw": bw,
            "area": area,
        })
    return nets, straight_nets


def _compute_net_interconnections(net_nodes: dict[int, set[int]], abs_pos: AbsPos) -> dict[int, set[int]]:
    """Phase 3b: build connected_nets dict.

    Two nets are interconnected if they share at least one abs position.
    Returns dict  root -> set of interconnected roots.
    """
    net_positions: dict[int, set[tuple[int, int]]] = {}
    for root, node_ids in net_nodes.items():
        net_positions[root] = {abs_pos[n] for n in node_ids}

    pos_to_roots: dict[tuple[int, int], set[int]] = {}
    for root, positions in net_positions.items():
        for pos in positions:
            pos_to_roots.setdefault(pos, set()).add(root)

    connected_nets: dict[int, set[int]] = {}
    for pos, roots in pos_to_roots.items():
        if len(roots) > 1:
            for r in roots:
                connected_nets.setdefault(r, set()).update(roots - {r})
    return connected_nets


# ---------------------------------------------------------------------------
# Occupancy grid
# ---------------------------------------------------------------------------

class _OccupancyGrid:
    """2D occupancy grid for orthogonal routing.

    Manages hard/soft blocking, wire cell tracking, and grid <-> world
    coordinate conversions.
    """

    GRID: int = GRID_UNIT
    MARGIN: int = 30
    CLEARANCE: int = 1
    CROSS_PENALTY: int = 100
    BEND_PENALTY: int = 1

    min_gx: int
    min_gy: int
    gcols: int
    grows: int
    hard_blocked: set[tuple[int, int]]
    soft_blocked: dict[tuple[int, int], set[int]]
    wire_cells: set[tuple[int, int]]
    wire_dirs: dict[tuple[int, int], set[str]]
    wire_cell_owners: dict[tuple[int, int, str], set[int]]
    pin_depart: dict[int, tuple[int, int]]
    pin_body: dict[int, tuple[int, int, int, int]]
    blocked: set[tuple[int, int]]

    def __init__(self, abs_pos: AbsPos, num_original: int, components: list[CompDict] | None) -> None:
        orig_xs: list[int] = [abs_pos[i][0] for i in range(num_original)]
        orig_ys: list[int] = [abs_pos[i][1] for i in range(num_original)]

        self.min_gx = min(orig_xs) // self.GRID - self.MARGIN
        self.min_gy = min(orig_ys) // self.GRID - self.MARGIN
        max_gx: int = max(orig_xs) // self.GRID + self.MARGIN
        max_gy: int = max(orig_ys) // self.GRID + self.MARGIN
        self.gcols = max_gx - self.min_gx + 1
        self.grows = max_gy - self.min_gy + 1

        self.hard_blocked = set()
        self.soft_blocked = {}      # (col, row) -> set of nids
        self.wire_cells = set()
        self.wire_dirs = {}         # (col, row) -> set of axes ('H' / 'V')
        self.wire_cell_owners = {}  # (col, row, axis) -> set of net roots
        self.pin_depart = {}        # nid -> (dc, dr)
        self.pin_body = {}          # nid -> (bx0, bx1, by0, by1) grid coords

        self._populate_blocking(abs_pos, num_original, components)

        # Effective blocked = hard + soft
        self.blocked = set(self.hard_blocked)
        for cell in self.soft_blocked:
            self.blocked.add(cell)

        _log.debug(
            "grid=%dx%d min_gx=%d min_gy=%d hard=%d soft=%d total_blocked=%d",
            self.gcols, self.grows, self.min_gx, self.min_gy,
            len(self.hard_blocked), len(self.soft_blocked), len(self.blocked))

    # -- coordinate helpers --------------------------------------------------

    def col(self, x: int) -> int:
        """Convert deci-grid x to grid column."""
        return x // self.GRID - self.min_gx

    def row(self, y: int) -> int:
        """Convert deci-grid y to grid row."""
        return y // self.GRID - self.min_gy

    def to_world(self, c: int, r: int) -> tuple[int, int]:
        """Convert grid (col, row) to deci-grid (x, y)."""
        return (c + self.min_gx) * self.GRID, (r + self.min_gy) * self.GRID

    # -- wire tracking -------------------------------------------------------

    def mark_straight_nets(self, straight_nets: list[tuple[int, int, int, int, int]]) -> None:
        """Pre-mark straight wire nets in wire_cells."""
        for sn_root, sn_x0, sn_y0, sn_x1, sn_y1 in straight_nets:
            gc0: int = sn_x0 // self.GRID - self.min_gx
            gr0: int = sn_y0 // self.GRID - self.min_gy
            gc1: int = sn_x1 // self.GRID - self.min_gx
            gr1: int = sn_y1 // self.GRID - self.min_gy
            if gc0 == gc1:  # vertical
                for r in range(min(gr0, gr1), max(gr0, gr1) + 1):
                    self.wire_cells.add((gc0, r))
                    self.wire_dirs.setdefault((gc0, r), set()).add('V')
                    self.wire_cell_owners.setdefault((gc0, r, 'V'), set()).add(sn_root)
            else:  # horizontal
                for c in range(min(gc0, gc1), max(gc0, gc1) + 1):
                    self.wire_cells.add((c, gr0))
                    self.wire_dirs.setdefault((c, gr0), set()).add('H')
                    self.wire_cell_owners.setdefault((c, gr0, 'H'), set()).add(sn_root)

    def mark_wire(self, full_path: list[tuple[int, int]], net_root: int, net_cells: set[tuple[int, int]]) -> None:
        """Record routed wire segments after a successful route."""
        for i in range(len(full_path) - 1):
            c0, r0 = full_path[i]
            c1, r1 = full_path[i + 1]
            if c0 == c1:
                for r in range(min(r0, r1), max(r0, r1) + 1):
                    net_cells.add((c0, r))
                    self.wire_cells.add((c0, r))
                    self.wire_dirs.setdefault((c0, r), set()).add('V')
                    self.wire_cell_owners.setdefault((c0, r, 'V'), set()).add(net_root)
            elif r0 == r1:
                for c in range(min(c0, c1), max(c0, c1) + 1):
                    net_cells.add((c, r0))
                    self.wire_cells.add((c, r0))
                    self.wire_dirs.setdefault((c, r0), set()).add('H')
                    self.wire_cell_owners.setdefault((c, r0, 'H'), set()).add(net_root)

    # -- blocking management -------------------------------------------------

    def unlock_soft(self, nids: set[int]) -> set[tuple[int, int]]:
        """Temporarily unblock soft_blocked cells owned by *nids*.

        Returns the set of cells that were unblocked (caller must relock).
        """
        temp_unblocked: set[tuple[int, int]] = set()
        for cell, nid_set in self.soft_blocked.items():
            if nids & nid_set and cell in self.blocked:
                self.blocked.discard(cell)
                temp_unblocked.add(cell)
        return temp_unblocked

    def unlock_net_cells(self, net_cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
        """Temporarily unblock cells already routed for the current net.

        Returns the set of cells that were unblocked (caller must relock).
        """
        restored: set[tuple[int, int]] = set()
        for cell in net_cells:
            if cell in self.blocked:
                self.blocked.discard(cell)
                restored.add(cell)
        return restored

    def relock(self, cells: set[tuple[int, int]]) -> None:
        """Re-add previously unblocked cells to the blocked set."""
        for cell in cells:
            self.blocked.add(cell)

    # -- internal ------------------------------------------------------------

    def _populate_blocking(self, abs_pos: AbsPos, num_original: int, components: list[CompDict] | None) -> None:
        """Build hard_blocked, soft_blocked, pin_depart, pin_body from components."""
        if not components:
            return

        from synthesis.gates.registry import dimensions as _ref_dimensions

        for comp in components:
            cx: int = comp.get("x", 0)
            cy: int = comp.get("y", 0)
            ct: str = comp.get("objectType", "")
            cd: dict[str, Any] = comp.get("customData", {}).get("nodes", {})
            comp_nids: list[int] = []
            for val in cd.values():
                if isinstance(val, int) and val < num_original:
                    comp_nids.append(val)
                elif isinstance(val, list):
                    for nid in val:
                        if isinstance(nid, int) and nid < num_original:
                            comp_nids.append(nid)
            if not comp_nids:
                continue

            # Body size from reference dimensions (or inline for subcircuits)
            sc_dim: dict[str, int] | None = comp.get("customData", {}).get("_sc_dimensions")
            dim: dict[str, int]
            if sc_dim:
                dim = sc_dim
            elif ct:
                params: dict[str, Any] = _extract_comp_params(ct, comp)
                try:
                    dim = _ref_dimensions(ct, **params)
                except KeyError:
                    _log.debug("_populate_blocking: dimensions lookup failed for '%s', using default 20x20", ct)
                    dim = {"left": 20, "right": 20, "up": 20, "down": 20}
            else:
                dim = {"left": 20, "right": 20, "up": 20, "down": 20}

            # Body bounding box in grid coords + CLEARANCE ring
            body_x0: int = (cx - dim["left"]) // self.GRID - self.CLEARANCE
            body_x1: int = (cx + dim["right"]) // self.GRID + self.CLEARANCE
            body_y0: int = (cy - dim["up"]) // self.GRID - self.CLEARANCE
            body_y1: int = (cy + dim["down"]) // self.GRID + self.CLEARANCE
            for gx in range(body_x0, body_x1 + 1):
                for gy in range(body_y0, body_y1 + 1):
                    c: int = gx - self.min_gx
                    r: int = gy - self.min_gy
                    if 0 <= c < self.gcols and 0 <= r < self.grows:
                        self.hard_blocked.add((c, r))

            # Per-pin: departure direction + soft_blocked corridor
            for nid in comp_nids:
                pc: int = abs_pos[nid][0] // self.GRID - self.min_gx
                pr: int = abs_pos[nid][1] // self.GRID - self.min_gy
                rx: int = abs_pos[nid][0] - cx
                ry: int = abs_pos[nid][1] - cy
                if rx >= dim["right"]:
                    self.pin_depart[nid] = (1, 0)
                elif rx <= -dim["left"]:
                    self.pin_depart[nid] = (-1, 0)
                elif ry >= dim["down"]:
                    self.pin_depart[nid] = (0, 1)
                elif ry <= -dim["up"]:
                    self.pin_depart[nid] = (0, -1)
                else:
                    if abs(rx) >= abs(ry):
                        self.pin_depart[nid] = (1 if rx >= 0 else -1, 0)
                    else:
                        self.pin_depart[nid] = (0, 1 if ry >= 0 else -1)
                dep_dc: int
                dep_dr: int
                dep_dc, dep_dr = self.pin_depart[nid]
                _log.debug(
                    "PIN nid=%d abs=%s comp=%s@(%d,%d) rx=%d ry=%d "
                    "dim=l%dr%du%dd%d depart=%s",
                    nid, abs_pos[nid], ct, cx, cy,
                    rx, ry, dim['left'], dim['right'], dim['up'], dim['down'],
                    self.pin_depart[nid])

                # Body bounds in grid coords (relative to grid origin)
                bx0: int = body_x0 - self.min_gx
                bx1: int = body_x1 - self.min_gx
                by0: int = body_y0 - self.min_gy
                by1: int = body_y1 - self.min_gy
                self.pin_body[nid] = (bx0, bx1, by0, by1)

                # Pin cell -> soft_blocked
                if 0 <= pc < self.gcols and 0 <= pr < self.grows:
                    self.soft_blocked.setdefault((pc, pr), set()).add(nid)
                cc: int = pc + dep_dc
                cr: int = pr + dep_dr
                while (0 <= cc < self.gcols and 0 <= cr < self.grows
                       and bx0 <= cc <= bx1 and by0 <= cr <= by1):
                    self.soft_blocked.setdefault((cc, cr), set()).add(nid)
                    cc += dep_dc
                    cr += dep_dr
                # One more cell outside for clearance
                if 0 <= cc < self.gcols and 0 <= cr < self.grows:
                    self.soft_blocked.setdefault((cc, cr), set()).add(nid)


# ---------------------------------------------------------------------------
# A* maze router
# ---------------------------------------------------------------------------

def astar_route(grid: _OccupancyGrid, net_root: int, connected_nets: dict[int, set[int]], sc: int, sr: int, tc: int, tr: int) -> list[tuple[int, int]] | None:
    """A* shortest path on the occupancy grid.

    Wire cells may be crossed straight-through (perpendicular) but
    turning (bending) on a wire cell is forbidden --- a bend creates a
    connection point in CircuitVerse, which would short two nets.

    Returns list of (col, row) waypoints, or None if no path.
    """
    if sc == tc and sr == tr:
        return [(sc, sr)]

    INF: float = float("inf")
    best: dict[tuple[int, int, int], float] = {}
    prev: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    pq: list[tuple[float, float, int, int, int]] = []
    g0: float = 0
    h0: int = abs(sc - tc) + abs(sr - tr)
    heapq.heappush(pq, (g0 + h0, g0, sc, sr, -1))
    best[(sc, sr, -1)] = g0

    gcols: int = grid.gcols
    grows: int = grid.grows
    blocked: set[tuple[int, int]] = grid.blocked
    wire_cells: set[tuple[int, int]] = grid.wire_cells
    wire_dirs: dict[tuple[int, int], set[str]] = grid.wire_dirs
    wire_cell_owners: dict[tuple[int, int, str], set[int]] = grid.wire_cell_owners
    cross_penalty: int = grid.CROSS_PENALTY
    bend_penalty: int = grid.BEND_PENALTY

    while pq:
        f, g, c, r, d = heapq.heappop(pq)
        if g > best.get((c, r, d), INF):
            continue
        if c == tc and r == tr:
            # Reconstruct
            path: list[tuple[int, int]] = [(c, r)]
            state: tuple[int, int, int] = (c, r, d)
            while state in prev:
                state = prev[state]
                path.append((state[0], state[1]))
            path.reverse()
            # Extract waypoints (bend points only)
            if len(path) <= 2:
                return path
            waypoints: list[tuple[int, int]] = [path[0]]
            for i in range(1, len(path) - 1):
                pc, pr = path[i - 1]
                cc, cr = path[i]
                nc, nr = path[i + 1]
                if (nc - cc) != (cc - pc) or (nr - cr) != (cr - pr):
                    waypoints.append(path[i])
            waypoints.append(path[-1])
            return waypoints

        for i in range(4):
            nc: int = c + _DC[i]
            nr: int = r + _DR[i]
            if not (0 <= nc < gcols and 0 <= nr < grows):
                continue
            # Component body = impassable (unless it's the target pin)
            if (nc, nr) in blocked and not (nc == tc and nr == tr):
                continue
            # Forbid turning on a wire cell (bend = connection point
            # in CircuitVerse -> creates unintended short)
            # Allow if all wire owners at this cell are interconnected
            is_turn: bool = d != -1 and i != d
            if is_turn and (c, r) in wire_cells:
                all_owners: set[int] = set()
                for ax in wire_dirs.get((c, r), set()):
                    all_owners |= wire_cell_owners.get((c, r, ax), set())
                my_connected: set[int] = connected_nets.get(net_root, set())
                if not all_owners.issubset(my_connected | {net_root}):
                    continue
            # Forbid collinear movement along existing wire (overlap)
            # unless current net is interconnected with the wire owner
            step: int = 1
            move_axis: str = 'H' if i in (0, 2) else 'V'
            if (nc, nr) in wire_cells:
                owners: set[int] = wire_cell_owners.get((nc, nr, move_axis), set())
                if owners:
                    my_connected = connected_nets.get(net_root, set())
                    if not owners.issubset(my_connected | {net_root}):
                        continue  # unrelated net -- no overlap allowed
                step += cross_penalty
            if is_turn:
                step += bend_penalty
            ng: float = g + step
            if ng < best.get((nc, nr, i), INF):
                best[(nc, nr, i)] = ng
                prev[(nc, nr, i)] = (c, r, d)
                h: int = abs(nc - tc) + abs(nr - tr)
                heapq.heappush(pq, (ng + h, ng, nc, nr, i))

    return None  # truly no path


# ---------------------------------------------------------------------------
# Single-net router (nearest-sink decomposition)
# ---------------------------------------------------------------------------

def _route_net(net: dict[str, Any], nodes: list[NodeDict], abs_pos: AbsPos, grid: _OccupancyGrid, connected_nets: dict[int, set[int]], pin_departure_fn: Callable[[int], tuple[int, int]]) -> None:
    """Route a single multi-pin net using nearest-sink decomposition.

    Modifies *nodes* (adds bend nodes, wires connections) and *abs_pos*
    (appends positions for new bend nodes) in place.
    """
    bw: int = net["bw"]
    node_ids: set[int] = net["node_ids"]
    net_root: int = net["root"]

    # Remove existing direct connections within this net
    existing_pairs: set[tuple[int, int]] = set()
    for nid in node_ids:
        for conn in list(nodes[nid]["connections"]):
            if conn in node_ids:
                existing_pairs.add((min(nid, conn), max(nid, conn)))
    for a, b in existing_pairs:
        _disconnect(nodes, a, b)

    # Nearest-sink decomposition
    nid_list: list[int] = list(node_ids)
    routed_set: set[int] = {nid_list[0]}
    remaining: set[int] = set(nid_list[1:])
    net_cells: set[tuple[int, int]] = set()

    while remaining:
        # Find nearest unrouted node to any routed node
        best_pair: tuple[int, int] | None = None
        best_dist: float = float("inf")
        for src in routed_set:
            sx, sy = abs_pos[src]
            for dst in remaining:
                dx, dy = abs_pos[dst]
                dist: int = abs(sx - dx) + abs(sy - dy)
                if dist < best_dist:
                    best_dist = dist
                    best_pair = (src, dst)

        assert best_pair is not None
        src, dst = best_pair
        sx, sy = abs_pos[src]
        dx, dy = abs_pos[dst]

        sc: int = grid.col(sx)
        sr: int = grid.row(sy)
        tc: int = grid.col(dx)
        tr: int = grid.row(dy)

        # Same grid cell -- just wire directly
        if sc == tc and sr == tr:
            _wire(nodes, src, dst)
            routed_set.add(dst)
            remaining.discard(dst)
            continue

        # Compute A* endpoints: walk from pin through own body only.
        src_dc: int
        src_dr: int
        src_dc, src_dr = pin_departure_fn(src)
        astar_sc: int = sc + src_dc
        astar_sr: int = sr + src_dr
        if src in grid.pin_body:
            bx0, bx1, by0, by1 = grid.pin_body[src]
            while bx0 <= astar_sc <= bx1 and by0 <= astar_sr <= by1:
                astar_sc += src_dc
                astar_sr += src_dr
        else:
            while (astar_sc, astar_sr) in grid.hard_blocked:
                astar_sc += src_dc
                astar_sr += src_dr

        # Nudge src departure off existing wires
        src_prenudge: tuple[int, int] | None = None
        if (astar_sc, astar_sr) in grid.wire_cells:
            for pdc, pdr in [(src_dr, -src_dc), (-src_dr, src_dc)]:
                nc, nr = astar_sc + pdc, astar_sr + pdr
                if (nc, nr) not in grid.wire_cells and (nc, nr) not in grid.blocked:
                    src_prenudge = (astar_sc, astar_sr)
                    astar_sc, astar_sr = nc, nr
                    break

        dst_dc: int
        dst_dr: int
        dst_dc, dst_dr = pin_departure_fn(dst)
        astar_tc: int = tc + dst_dc
        astar_tr: int = tr + dst_dr
        if dst in grid.pin_body:
            bx0, bx1, by0, by1 = grid.pin_body[dst]
            while bx0 <= astar_tc <= bx1 and by0 <= astar_tr <= by1:
                astar_tc += dst_dc
                astar_tr += dst_dr
        else:
            while (astar_tc, astar_tr) in grid.hard_blocked:
                astar_tc += dst_dc
                astar_tr += dst_dr

        # Nudge dst departure off existing wires
        dst_prenudge: tuple[int, int] | None = None
        if (astar_tc, astar_tr) in grid.wire_cells:
            for pdc, pdr in [(dst_dr, -dst_dc), (-dst_dr, dst_dc)]:
                nc, nr = astar_tc + pdc, astar_tr + pdr
                if (nc, nr) not in grid.wire_cells and (nc, nr) not in grid.blocked:
                    dst_prenudge = (astar_tc, astar_tr)
                    astar_tc, astar_tr = nc, nr
                    break

        # Temporarily unlock soft_blocked cells for src/dst pins
        temp_unblocked: set[tuple[int, int]] = grid.unlock_soft({src, dst})
        # Temporarily unblock already-routed cells of THIS net
        restored: set[tuple[int, int]] = grid.unlock_net_cells(net_cells)

        # A* from departure to arrival
        _log.debug(
            "ROUTE src=%d abs=(%d,%d) grid=(%d,%d) depart=(%d,%d) "
            "dst=%d abs=(%d,%d) grid=(%d,%d) arrive=(%d,%d)",
            src, sx, sy, sc, sr, astar_sc, astar_sr,
            dst, dx, dy, tc, tr, astar_tc, astar_tr)
        path: list[tuple[int, int]] | None = astar_route(grid, net_root, connected_nets,
                           astar_sc, astar_sr, astar_tc, astar_tr)
        if path:
            _log.debug("PATH: %s", ' -> '.join(f'({c},{r})' for c, r in path))
        else:
            _log.debug("PATH: None (no path found)")

        # Restore all temporarily unblocked cells
        grid.relock(temp_unblocked)
        grid.relock(restored)

        if path is None:
            _log.warning(
                "ROUTE FAIL: %d(%d,%d)->%d(%d,%d) depart(%d,%d)->(%d,%d) "
                "grid=%dx%d blk=%d",
                src, sx, sy, dst, dx, dy,
                astar_sc, astar_sr, astar_tc, astar_tr,
                grid.gcols, grid.grows, len(grid.blocked))
            _wire(nodes, src, dst)
            routed_set.add(dst)
            remaining.discard(dst)
            continue

        # Trim collinear escape segments: skip the first/last A* waypoint
        # when the escape direction and the adjacent path segment share
        # the same axis (both H or both V).
        render_path: list[tuple[int, int]] = list(path)
        if src_prenudge is None and len(render_path) >= 2:
            seg_dc: int = render_path[1][0] - render_path[0][0]
            seg_dr: int = render_path[1][1] - render_path[0][1]
            if _same_axis(src_dc, src_dr, seg_dc, seg_dr):
                render_path = render_path[1:]
        if dst_prenudge is None and len(render_path) >= 2:
            seg_dc = render_path[-1][0] - render_path[-2][0]
            seg_dr = render_path[-1][1] - render_path[-2][1]
            if _same_axis(dst_dc, dst_dr, seg_dc, seg_dr):
                render_path = render_path[:-1]

        # Wire: src_pin -> [departure -> A* path -> arrival] -> dst_pin
        prev_nid: int = src
        if src_prenudge is not None:
            wx: int
            wy: int
            wx, wy = grid.to_world(src_prenudge[0], src_prenudge[1])
            bend: int = _make_bend(nodes, abs_pos, wx, wy, bw)
            _wire(nodes, prev_nid, bend)
            prev_nid = bend
        for i in range(len(render_path)):
            wx, wy = grid.to_world(render_path[i][0], render_path[i][1])
            bend = _make_bend(nodes, abs_pos, wx, wy, bw)
            _wire(nodes, prev_nid, bend)
            prev_nid = bend
        if dst_prenudge is not None:
            wx, wy = grid.to_world(dst_prenudge[0], dst_prenudge[1])
            bend = _make_bend(nodes, abs_pos, wx, wy, bw)
            _wire(nodes, prev_nid, bend)
            prev_nid = bend
        _wire(nodes, prev_nid, dst)

        # Mark routed wire cells (including pre-nudge segments)
        src_pre: list[tuple[int, int]] = [src_prenudge] if src_prenudge else []
        dst_pre: list[tuple[int, int]] = [dst_prenudge] if dst_prenudge else []
        full_path: list[tuple[int, int]] = [(sc, sr)] + src_pre + list(path) + dst_pre + [(tc, tr)]
        grid.mark_wire(full_path, net_root, net_cells)

        routed_set.add(dst)
        remaining.discard(dst)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def route_orthogonal(nodes: list[NodeDict], abs_pos: AbsPos, components: list[CompDict] | None = None) -> None:
    """Insert intermediate type-2 nodes so all wires are orthogonal.

    Uses A* maze routing on a 2D occupancy grid.  Component bounding
    boxes are marked as blocked so wires never pass through component
    bodies.

    Args:
        nodes: mutable list of node dicts (na.nodes)
        abs_pos: mutable list of (x, y) tuples (na.abs_pos)
        components: list of component dicts (or None)
    """
    num_original: int = len(nodes)

    # Phase 1: collect connection pairs
    pairs: set[tuple[int, int]] = _collect_pairs(nodes, num_original)
    if not pairs:
        return

    # Phase 2: build nets via union-find
    uf: _UnionFind = _UnionFind(num_original)
    for a, b in pairs:
        uf.union(a, b)
    net_nodes: dict[int, set[int]] = {}
    for a, b in pairs:
        root: int = uf.find(a)
        net_nodes.setdefault(root, set()).update([a, b])

    # Phase 3: characterize nets
    nets: list[dict[str, Any]]
    straight_nets: list[tuple[int, int, int, int, int]]
    nets, straight_nets = _characterize_nets(net_nodes, nodes, abs_pos)
    if not nets:
        return

    # Phase 3b: precompute net interconnections
    connected_nets: dict[int, set[int]] = _compute_net_interconnections(net_nodes, abs_pos)

    # Phase 4: build occupancy grid
    grid: _OccupancyGrid = _OccupancyGrid(abs_pos, num_original, components)
    grid.mark_straight_nets(straight_nets)

    # Pin departure callback (needs both grid.pin_depart and nodes)
    def _pin_departure(nid: int) -> tuple[int, int]:
        if nid in grid.pin_depart:
            return grid.pin_depart[nid]
        nt: int = nodes[nid]["type"]
        if nt == 1:
            return (1, 0)
        elif nt == 0:
            return (-1, 0)
        return (1, 0)

    # Phase 6: route each net (smallest area first)
    nets.sort(key=lambda n: n["area"], reverse=True)
    for net_idx, net in enumerate(nets):
        _log.info("NET %d/%d nodes=%d bw=%d",
                  net_idx, len(nets), len(net['node_ids']), net['bw'])
        _route_net(net, nodes, abs_pos, grid, connected_nets, _pin_departure)
