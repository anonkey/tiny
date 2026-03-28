"""Routing verification checks for CircuitVerse exports.

Each check is a
standalone function that returns an issue count and logs warnings.
"""
from __future__ import annotations

import logging

from common.constants import GRID_UNIT
from common.types import AbsPos, CompDict, NodeDict
from common.utils import _extract_comp_params

# A net: (node_ids, cells, segments, junction_cells)
Net = tuple[set[int], set[tuple[int, int]], set[tuple[str, int, int, int]], set[tuple[int, int]]]

_log: logging.Logger = logging.getLogger(__name__)

GRID: int = GRID_UNIT


def _collect_comp_pin_nids(components: list[CompDict] | None) -> set[int]:
    """Extract pin node IDs from component dicts.

    Returns set[int] of all node IDs that belong to component pins.
    """
    pin_nids: set[int] = set()
    if not components:
        return pin_nids
    for comp in components:
        cd = comp.customData.nodes
        for val in cd.values():
            if isinstance(val, int):
                pin_nids.add(val)
            elif isinstance(val, list):
                for nid in val:
                    if isinstance(nid, int):
                        pin_nids.add(nid)
    return pin_nids


def _build_node_to_comp(components: list[CompDict] | None) -> dict[int, tuple[str, str, str]]:
    """Build reverse map: node ID -> (objectType, label, pin_name).

    Returns empty dict when components is None.
    """
    mapping: dict[int, tuple[str, str, str]] = {}
    if not components:
        return mapping
    for comp in components:
        ct = comp.objectType or "SubCircuit"
        lbl = comp.label or ""
        cd = comp.customData.nodes
        for pin_name, val in cd.items():
            if isinstance(val, int):
                mapping[val] = (ct, lbl, pin_name)
            elif isinstance(val, list):
                for nid in val:
                    if isinstance(nid, int):
                        mapping[nid] = (ct, lbl, pin_name)
    return mapping


def _fmt_node_owner(nid: int, node_to_comp: dict[int, tuple[str, str, str]]) -> str:
    """Format a node's owner info, e.g. 'Input "i_data".inp1' or 'bend'."""
    if nid in node_to_comp:
        ct, lbl, pin = node_to_comp[nid]
        label_part = f' "{lbl}"' if lbl else ""
        return f"{ct}{label_part}.{pin}"
    return "bend"


def _dump_debug(
    nodes: list[NodeDict],
    abs_pos: AbsPos,
    nets: list[Net],
    node_to_comp: dict[int, tuple[str, str, str]],
    comp_pin_nids: set[int],
) -> None:
    """Dump full topology at DEBUG level for diagnosis."""
    _log.debug("=== NODE-TO-COMPONENT MAP ===")
    for nid, (ct, lbl, pin) in sorted(node_to_comp.items()):
        ax, ay = abs_pos[nid]
        _log.debug("  node %d (%d,%d) bw=%d -> %s \"%s\" pin=%s",
                    nid, ax, ay, nodes[nid].bitWidth, ct, lbl, pin)

    _log.debug("=== NETS (%d total) ===", len(nets))
    for ni, (nids, _, segs, junctions) in enumerate(nets):
        _log.debug("--- net %d  (%d nodes) ---", ni, len(nids))
        for nid in sorted(nids):
            ax, ay = abs_pos[nid]
            node = nodes[nid]
            owner = _fmt_node_owner(nid, node_to_comp)
            pin_mark = "P" if nid in comp_pin_nids else "W"
            _log.debug("  [%s] node %d (%d,%d) type=%d bw=%d conns=%s  owner=%s",
                        pin_mark, nid, ax, ay, node.type, node.bitWidth,
                        node.connections, owner)
        for seg in sorted(segs):
            _log.debug("  seg %s coord=%d range=[%d,%d]", seg[0], seg[1], seg[2], seg[3])
        if junctions:
            _log.debug("  junctions: %s", sorted(junctions))


def _collect_nets(nodes: list[NodeDict], abs_pos: AbsPos) -> tuple[list[Net], int]:
    """BFS net discovery, segment/cell collection, diagonal detection.

    Returns (nets, diag_issues) where each net is
    (nids, cells, segments, junction_cells).
    """
    issues: int = 0
    visited: set[int] = set()
    nets: list[Net] = []

    for start in range(len(nodes)):
        if start in visited or not nodes[start].connections:
            continue
        net_nids: set[int] = set()
        queue: list[int] = [start]
        while queue:
            nid = queue.pop(0)
            if nid in net_nids:
                continue
            net_nids.add(nid)
            for cid in nodes[nid].connections:
                if cid not in net_nids:
                    queue.append(cid)
        visited |= net_nids

        net_cells: set[tuple[int, int]] = set()
        net_segments: set[tuple[str, int, int, int]] = set()
        for nid in net_nids:
            ax, ay = abs_pos[nid]
            for cid in nodes[nid].connections:
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

        junction_cells: set[tuple[int, int]] = set()
        for nid in net_nids:
            if len(nodes[nid].connections) >= 3:
                junction_cells.add(abs_pos[nid])
        nets.append((net_nids, net_cells, net_segments, junction_cells))

    return nets, issues


def _check_visual_shorts(nets: list[Net]) -> int:
    """Detect junction-on-junction shorts between different nets.

    Returns issue count.
    """
    issues: int = 0
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


def _check_segment_overlaps(nets: list[Net], node_to_comp: dict[int, tuple[str, str, str]]) -> int:
    """Detect collinear segment overlaps between different nets.

    Returns issue count.
    """
    issues: int = 0
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
                        owners_i = {_fmt_node_owner(n, node_to_comp) for n in nets[i][0] if n in node_to_comp}
                        owners_j = {_fmt_node_owner(n, node_to_comp) for n in nets[j][0] if n in node_to_comp}
                        _log.warning("OVERLAP: nets (node %d...) and (node %d...) "
                                     "%s at %s=%d range [%d,%d]"
                                     "  net_a=%s  net_b=%s",
                                     sample_i, sample_j, seg_i[0],
                                     'y' if seg_i[0] == 'H' else 'x',
                                     seg_i[1], shared_start, shared_end,
                                     owners_i or "{no pins}", owners_j or "{no pins}")
    return issues


def _check_endpoints_on_wires(
    nets: list[Net], abs_pos: AbsPos, comp_pin_nids: set[int],
    nodes: list[NodeDict], node_to_comp: dict[int, tuple[str, str, str]],
) -> int:
    """Detect wire endpoints landing on another net's segment.

    Returns issue count.
    """
    issues: int = 0
    for i, (nids_i, _, segs_i, _) in enumerate(nets):
        for nid in nids_i:
            if nid in comp_pin_nids:
                continue
            ax, ay = abs_pos[nid]
            node = nodes[nid]
            for j, (_, _, segs_j, _) in enumerate(nets):
                if i == j:
                    continue
                for seg in segs_j:
                    if seg[0] == 'H' and ay == seg[1] and seg[2] < ax < seg[3]:
                        issues += 1
                        sample_j = min(nets[j][0])
                        _log.warning("ENDPOINT_ON_WIRE: node %d(%d,%d) type=%d conns=%s "
                                     "lands on net (node %d...) "
                                     "H segment y=%d x=[%d,%d]",
                                     nid, ax, ay, node.type, node.connections,
                                     sample_j, seg[1], seg[2], seg[3])
                    elif seg[0] == 'V' and ax == seg[1] and seg[2] < ay < seg[3]:
                        issues += 1
                        sample_j = min(nets[j][0])
                        _log.warning("ENDPOINT_ON_WIRE: node %d(%d,%d) type=%d conns=%s "
                                     "lands on net (node %d...) "
                                     "V segment x=%d y=[%d,%d]",
                                     nid, ax, ay, node.type, node.connections,
                                     sample_j, seg[1], seg[2], seg[3])
    return issues


def _check_clearance_violations(nets: list[Net], abs_pos: AbsPos, components: list[CompDict] | None) -> int:
    """Detect wire segments crossing component bodies.

    Returns issue count.
    """
    if not components:
        return 0

    from synthesis.gates.registry import dimensions as _ref_dimensions

    issues: int = 0
    for comp in components:
        cx, cy = comp.x, comp.y
        ct = comp.objectType
        # Support both base components (registry lookup) and subcircuits
        # (inline _sc_dimensions) — same clearance rules for both.
        sc_dim = comp.customData._sc_dimensions
        if sc_dim:
            dim = sc_dim
        elif ct:
            params = _extract_comp_params(ct, comp)
            try:
                dim = _ref_dimensions(ct, **params)
            except KeyError:
                continue
        else:
            continue

        bx0 = cx - dim["left"] + 1
        bx1 = cx + dim["right"] - 1
        by0 = cy - dim["up"] + 1
        by1 = cy + dim["down"] - 1

        own_nids: set[int] = set()
        cd = comp.customData.nodes
        for val in cd.values():
            if isinstance(val, int):
                own_nids.add(val)
            elif isinstance(val, list):
                for nid in val:
                    if isinstance(nid, int):
                        own_nids.add(nid)

        own_pin_pos: set[tuple[int, int]] = {abs_pos[nid] for nid in own_nids}

        for _, _, net_segs, _ in nets:
            for seg in net_segs:
                if seg[0] == 'H':
                    sy = seg[1]
                    sx0, sx1 = seg[2], seg[3]
                    if by0 <= sy <= by1 and sx0 < bx1 and sx1 > bx0:
                        if any(py == sy and sx0 <= px <= sx1 for px, py in own_pin_pos):
                            continue
                        issues += 1
                        label = ct or "SubCircuit"
                        _log.warning("CLEARANCE: H wire y=%d x=[%d,%d] "
                                     "crosses %s@(%d,%d) body [%d,%d]x[%d,%d]",
                                     sy, sx0, sx1, label, cx, cy,
                                     cx - dim['left'], cx + dim['right'],
                                     cy - dim['up'], cy + dim['down'])
                elif seg[0] == 'V':
                    sx = seg[1]
                    sy0, sy1 = seg[2], seg[3]
                    if bx0 <= sx <= bx1 and sy0 < by1 and sy1 > by0:
                        if any(px == sx and sy0 <= py <= sy1 for px, py in own_pin_pos):
                            continue
                        issues += 1
                        label = ct or "SubCircuit"
                        _log.warning("CLEARANCE: V wire x=%d y=[%d,%d] "
                                     "crosses %s@(%d,%d) body [%d,%d]x[%d,%d]",
                                     sx, sy0, sy1, label, cx, cy,
                                     cx - dim['left'], cx + dim['right'],
                                     cy - dim['up'], cy + dim['down'])
    return issues


def _check_bitwidth_mismatches(nets: list[Net], nodes: list[NodeDict]) -> int:
    """Detect connected nodes with different bitWidths.

    Returns issue count.
    """
    issues: int = 0
    for net_nids, _, _, _ in nets:
        bws: dict[int, list[int]] = {}
        for nid in net_nids:
            bw = nodes[nid].bitWidth
            bws.setdefault(bw, []).append(nid)
        if len(bws) > 1:
            issues += 1
            parts = ", ".join(f"bw={bw}: nodes {sorted(nids)[:3]}"
                              for bw, nids in sorted(bws.items()))
            _log.warning("BW_MISMATCH: net has mixed bitwidths — %s", parts)
    return issues


def _check_hanging_wires(
    nets: list[Net], abs_pos: AbsPos, comp_pin_nids: set[int],
    nodes: list[NodeDict], node_to_comp: dict[int, tuple[str, str, str]],
) -> int:
    """Detect wire endpoints that don't terminate on a component pin.

    A hanging wire is a node with exactly 1 connection (degree-1 endpoint)
    that isn't a component pin — it's a routing node dangling in mid-air.

    Returns issue count.
    """
    issues: int = 0
    for net_nids, _, _, _ in nets:
        for nid in net_nids:
            if len(nodes[nid].connections) == 1 and nid not in comp_pin_nids:
                ax, ay = abs_pos[nid]
                issues += 1
                target = nodes[nid].connections[0]
                target_owner = _fmt_node_owner(target, node_to_comp)
                _log.warning("HANGING: node %d(%d,%d) type=%d has 1 connection "
                             "-> node %d (%s) but is not a component pin",
                             nid, ax, ay, nodes[nid].type, target, target_owner)
    return issues


def verify_routing(nodes: list[NodeDict], abs_pos: AbsPos, components: list[CompDict] | None = None) -> int:
    """Check for routing issues: diagonals, visual shorts, clearance, endpoints-on-wire, hanging wires.

    Prints warnings to stderr.  Returns number of issues found.
    """
    comp_pin_nids: set[int] = _collect_comp_pin_nids(components)
    node_to_comp: dict[int, tuple[str, str, str]] = _build_node_to_comp(components)
    nets: list[Net]
    nets, issues = _collect_nets(nodes, abs_pos)

    if _log.isEnabledFor(logging.DEBUG):
        _dump_debug(nodes, abs_pos, nets, node_to_comp, comp_pin_nids)

    issues += _check_visual_shorts(nets)
    issues += _check_segment_overlaps(nets, node_to_comp)
    issues += _check_endpoints_on_wires(nets, abs_pos, comp_pin_nids, nodes, node_to_comp)
    issues += _check_clearance_violations(nets, abs_pos, components)
    issues += _check_bitwidth_mismatches(nets, nodes)
    issues += _check_hanging_wires(nets, abs_pos, comp_pin_nids, nodes, node_to_comp)

    if issues == 0:
        _log.info("ROUTE OK: no issues found")
    else:
        _log.warning("ROUTE: %d issue(s) found", issues)
    return issues
