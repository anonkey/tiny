"""CircuitVerse node allocator."""


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
        from verification.verify import verify_routing as _verify
        return _verify(self.nodes, self.abs_pos, components)

    def route_orthogonal(self, components=None):
        """Insert intermediate type-2 nodes so all wires are orthogonal."""
        from routing.router import route_orthogonal as _route
        _route(self.nodes, self.abs_pos, components)
