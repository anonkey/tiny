"""Node remapping, wiring, and routing helpers for CircuitVerse generation."""
from __future__ import annotations

from common.node_alloc import _CVNodeAlloc
from common.types import CompDict, CompMap, BitNodes


def remap_comp_nodes(comps: list[CompDict], remap: dict[int, int]) -> None:
    """Remap node IDs in component customData.nodes dicts."""
    for comp in comps:
        cd = comp.customData
        for k, v in cd.nodes.items():
            if isinstance(v, int):
                cd.nodes[k] = remap[v]
            elif isinstance(v, list):
                cd.nodes[k] = [remap[x] for x in v]


def _set_node_abs_positions(na: _CVNodeAlloc, all_comps: list[CompDict]) -> None:
    """Scan placed components and set absolute positions for their nodes."""
    for comp in all_comps:
        cx, cy = comp.x, comp.y
        direction = comp.direction
        for val in comp.customData.nodes.values():
            if isinstance(val, int):
                na.set_parent_pos(val, cx, cy, direction)
            elif isinstance(val, list):
                for nid in val:
                    if isinstance(nid, int):
                        na.set_parent_pos(nid, cx, cy, direction)


def resolve_and_route(na: _CVNodeAlloc, cv_inputs: list[CompDict], cv_outputs: list[CompDict], cv_splitters: list[CompDict], components: CompMap,
                      extra_comps: list[CompDict] | None = None, check: bool = False) -> list[CompDict]:
    """Collect all components, set absolute positions, run orthogonal routing.

    Returns the full component list used for routing.
    """
    all_comps = cv_inputs + cv_outputs + cv_splitters
    for comp_list in components.values():
        all_comps.extend(comp_list)
    if extra_comps:
        all_comps.extend(extra_comps)
    _set_node_abs_positions(na, all_comps)
    na.route_orthogonal(all_comps)
    if check:
        na.verify_routing(all_comps)
    return all_comps


def wire_nets(na: _CVNodeAlloc, bit_nodes: BitNodes) -> None:
    """Wire nodes sharing the same Yosys net — chain topology."""
    for _, node_ids in bit_nodes.items():
        for i in range(len(node_ids) - 1):
            na.connect(node_ids[i], node_ids[i + 1])


def wired_node_ids(na: _CVNodeAlloc) -> list[int]:
    """Return sorted IDs of wired (type-2, connected) nodes."""
    return sorted(
        i for i, n in enumerate(na.nodes)
        if n.type == 2 and n.connections
    )
