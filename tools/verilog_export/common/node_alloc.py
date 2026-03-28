"""CircuitVerse node allocator."""

from __future__ import annotations

from typing import Any

from common.types import NodeDict, AbsPos, CompDict


class _CVNodeAlloc:
    """Allocate sequential node IDs for CircuitVerse allNodes list."""

    nodes: list[NodeDict]
    abs_pos: AbsPos

    def __init__(self) -> None:
        self.nodes = []
        self.abs_pos = []

    def alloc(self, x: int, y: int, ntype: int, bit_width: int,
              label: str = "", parent_id: int | None = None) -> int:
        nid: int = len(self.nodes)
        self.nodes.append(NodeDict(
            x=x, y=y, type=ntype, bitWidth=bit_width,
            label=label,
        ))
        self.abs_pos.append((0, 0))  # set later via set_parent_pos
        return nid

    def set_parent_pos(self, nid: int, parent_x: int, parent_y: int,
                       direction: str = "RIGHT") -> None:
        """Record the absolute position of a node (parent pos + relative).

        Pin coordinates are stored in RIGHT orientation.  For LEFT-direction
        components the x axis must be mirrored so that ``abs_pos`` reflects
        the *visual* position used by the router.
        """
        n: NodeDict = self.nodes[nid]
        nx: int = -n.x if direction == "LEFT" else n.x
        self.abs_pos[nid] = (parent_x + nx, parent_y + n.y)

    def connect(self, a: int, b: int) -> None:
        self.nodes[a].connect(b)
        self.nodes[b].connect(a)

    def disconnect(self, a: int, b: int) -> None:
        """Remove the edge between nodes *a* and *b*."""
        self.nodes[a].disconnect(b)
        self.nodes[b].disconnect(a)

    def create_bend(self, x: int, y: int, bw: int, grid: int = 10) -> int:
        """Create a type-2 bend node. Returns the new node ID."""
        from common.constants import GRID_UNIT
        g: int = grid or GRID_UNIT
        x = round(x / g) * g
        y = round(y / g) * g
        nid: int = len(self.nodes)
        self.nodes.append(NodeDict(x=x, y=y, type=2, bitWidth=bw))
        self.abs_pos.append((x, y))
        return nid

    def nodes_as_dicts(self) -> list[dict[str, Any]]:
        """Serialize all nodes to plain dicts for JSON output."""
        return [n.to_dict() for n in self.nodes]

    def verify_routing(self, components: list[CompDict] | None = None) -> int:
        """Check for routing issues: diagonals, visual shorts, clearance, endpoints-on-wire.

        Prints warnings to stderr.  Returns number of issues found.
        """
        from verification.verify import verify_routing as _verify
        return _verify(self.nodes, self.abs_pos, components)

    def route_orthogonal(self, components: list[CompDict] | None = None) -> None:
        """Insert intermediate type-2 nodes so all wires are orthogonal."""
        from routing.router import route_orthogonal as _route
        _route(self.nodes, self.abs_pos, components)
