"""CircuitVerse node allocator."""

from __future__ import annotations

from common.types import NodeDict, AbsPos, CompDict


class _CVNodeAlloc:
    """Allocate sequential node IDs for CircuitVerse allNodes list."""

    nodes: list[NodeDict]
    abs_pos: AbsPos

    def __init__(self) -> None:
        self.nodes = []  # list of node dicts
        self.abs_pos = []  # (abs_x, abs_y) for each node

    def alloc(self, x: int, y: int, ntype: int, bit_width: int,
              label: str = "", parent_id: int | None = None) -> int:
        nid: int = len(self.nodes)
        node: NodeDict = {
            "x": x, "y": y,
            "type": ntype,  # 0=input, 1=output, 2=bidir
            "bitWidth": bit_width,
            "label": label,
            "connections": [],
        }
        self.nodes.append(node)
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
        nx: int = -n["x"] if direction == "LEFT" else n["x"]
        self.abs_pos[nid] = (parent_x + nx, parent_y + n["y"])

    def connect(self, a: int, b: int) -> None:
        if b not in self.nodes[a]["connections"]:
            self.nodes[a]["connections"].append(b)
        if a not in self.nodes[b]["connections"]:
            self.nodes[b]["connections"].append(a)

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
