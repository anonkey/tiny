"""Routing verification checks for CircuitVerse exports.

Split from cv_common.verify_routing() for clarity.  Each check is a
standalone function that returns an issue count and logs warnings.
"""

import logging

from circuitverse.components._common import GRID_UNIT
from cv_utils import _extract_comp_params

_log = logging.getLogger(__name__)

GRID = GRID_UNIT


def _collect_comp_pin_nids(components):
    """Extract pin node IDs from component dicts.

    Returns set[int] of all node IDs that belong to component pins.
    """
    pin_nids = set()
    if not components:
        return pin_nids
    for comp in components:
        cd = comp.get("customData", {}).get("nodes", {})
        for val in cd.values():
            if isinstance(val, int):
                pin_nids.add(val)
            elif isinstance(val, list):
                for nid in val:
                    if isinstance(nid, int):
                        pin_nids.add(nid)
    return pin_nids


def _collect_nets(nodes, abs_pos):
    """BFS net discovery, segment/cell collection, diagonal detection.

    Returns (nets, diag_issues) where each net is
    (nids, cells, segments, junction_cells).
    """
    issues = 0
    visited = set()
    nets = []

    for start in range(len(nodes)):
        if start in visited or not nodes[start]["connections"]:
            continue
        net_nids = set()
        queue = [start]
        while queue:
            nid = queue.pop(0)
            if nid in net_nids:
                continue
            net_nids.add(nid)
            for cid in nodes[nid]["connections"]:
                if cid not in net_nids:
                    queue.append(cid)
        visited |= net_nids

        net_cells = set()
        net_segments = set()
        for nid in net_nids:
            ax, ay = abs_pos[nid]
            for cid in nodes[nid]["connections"]:
                if cid > nid:
                    bx, by = abs_pos[cid]
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

        junction_cells = set()
        for nid in net_nids:
            if len(nodes[nid]["connections"]) >= 3:
                junction_cells.add(abs_pos[nid])
        nets.append((net_nids, net_cells, net_segments, junction_cells))

    return nets, issues


def _check_visual_shorts(nets):
    """Detect junction-on-junction shorts between different nets.

    Returns issue count.
    """
    issues = 0
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
    return issues


def _check_segment_overlaps(nets):
    """Detect collinear segment overlaps between different nets.

    Returns issue count.
    """
    issues = 0
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            for seg_i in nets[i][2]:
                for seg_j in nets[j][2]:
                    if seg_i[0] != seg_j[0]:
                        continue
                    if seg_i[1] != seg_j[1]:
                        continue
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
    return issues


def _check_endpoints_on_wires(nets, abs_pos, comp_pin_nids):
    """Detect wire endpoints landing on another net's segment.

    Returns issue count.
    """
    issues = 0
    for i, (nids_i, _, segs_i, _) in enumerate(nets):
        for nid in nids_i:
            if nid in comp_pin_nids:
                continue
            ax, ay = abs_pos[nid]
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
    return issues


def _check_clearance_violations(nets, abs_pos, components):
    """Detect wire segments crossing component bodies.

    Returns issue count.
    """
    if not components:
        return 0

    from circuitverse.components.registry import dimensions as _ref_dimensions

    issues = 0
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

        bx0 = cx - dim["left"] + 1
        bx1 = cx + dim["right"] - 1
        by0 = cy - dim["up"] + 1
        by1 = cy + dim["down"] - 1

        own_nids = set()
        cd = comp.get("customData", {}).get("nodes", {})
        for val in cd.values():
            if isinstance(val, int):
                own_nids.add(val)
            elif isinstance(val, list):
                for nid in val:
                    if isinstance(nid, int):
                        own_nids.add(nid)

        own_pin_pos = {abs_pos[nid] for nid in own_nids}

        for _, _, net_segs, _ in nets:
            for seg in net_segs:
                if seg[0] == 'H':
                    sy = seg[1]
                    sx0, sx1 = seg[2], seg[3]
                    if by0 <= sy <= by1 and sx0 < bx1 and sx1 > bx0:
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
                        if any(px == sx and sy0 <= py <= sy1 for px, py in own_pin_pos):
                            continue
                        issues += 1
                        _log.warning("CLEARANCE: V wire x=%d y=[%d,%d] "
                                     "crosses %s@(%d,%d) body [%d,%d]x[%d,%d]",
                                     sx, sy0, sy1, ct, cx, cy,
                                     cx - dim['left'], cx + dim['right'],
                                     cy - dim['up'], cy + dim['down'])
    return issues


def verify_routing(nodes, abs_pos, components=None):
    """Check for routing issues: diagonals, visual shorts, clearance, endpoints-on-wire.

    Prints warnings to stderr.  Returns number of issues found.
    """
    comp_pin_nids = _collect_comp_pin_nids(components)
    nets, issues = _collect_nets(nodes, abs_pos)

    issues += _check_visual_shorts(nets)
    issues += _check_segment_overlaps(nets)
    issues += _check_endpoints_on_wires(nets, abs_pos, comp_pin_nids)
    issues += _check_clearance_violations(nets, abs_pos, components)

    if issues == 0:
        _log.info("ROUTE OK: no issues found")
    else:
        _log.warning("ROUTE: %d issue(s) found", issues)
    return issues
