"""Shared type aliases and dataclasses for the verilog_export package."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, TypedDict


# ── Concrete type aliases ─────────────────────────────────────────────────

# CVCustomData.nodes values: single pin (int) or multi-pin array (list[int])
NodeValue = int | list[int]

# CVCustomData.constructorParamaters elements
CtorParam = str | int | list[int] | dict[str, int | bool | str]

# Yosys cell connections: port_name -> list of bit indices or constants
YosysConns = dict[str, list[int | str]]


# ── TypedDicts for structured dicts ──────────────────────────────────────

class YosysCell(TypedDict, total=False):
  """A single Yosys netlist cell."""
  type: str
  parameters: dict[str, str | int]
  port_directions: dict[str, str]
  connections: YosysConns
  attributes: dict[str, str | int]


class PortInfo(TypedDict):
  """Subcircuit port position and metadata."""
  direction: str
  width: int
  x: int
  y: int


class PinPos(TypedDict):
  """Minimal pin position on a subcircuit box."""
  x: int
  y: int


class SubScopeInfo(TypedDict):
  """Entry in sub_scope_ids dict."""
  scope_id: str
  port_info: dict[str, PortInfo]
  layout_w: int


class LayoutDict(TypedDict):
  """Return type of _cv_layout."""
  width: int
  height: int
  title_x: int
  title_y: int
  titleEnabled: bool


class NetInfo(TypedDict):
  """Router net descriptor."""
  root: int
  node_ids: set[int]
  min_x: int
  max_x: int
  min_y: int
  max_y: int
  bw: int
  area: int


class CVSubCircuit(TypedDict):
  """A SubCircuit entry in the CircuitVerse scope components dict."""
  x: int
  y: int
  id: str
  label: str
  labelDirection: str
  inputNodes: list[int]
  outputNodes: list[int]
  version: str


# Convenience aliases for col_cells repetition
CellEntry = tuple[str, YosysCell]
ColCells = dict[int, list[CellEntry]]


# ── Label direction mirror (used by CompDict.create) ─────────────────────
_LABEL_DIR: dict[str, str] = {
  "RIGHT": "LEFT", "LEFT": "RIGHT",
  "UP": "DOWN", "DOWN": "UP",
}


# ── Node dataclass ───────────────────────────────────────────────────────

@dataclass
class NodeDict:
  """A single CircuitVerse node (element of na.nodes / allNodes)."""
  x: int
  y: int
  type: int
  bitWidth: int
  label: str = ""
  connections: list[int] = field(default_factory=list)

  def connect(self, other_id: int) -> None:
    """Add other_id to connections if not present."""
    if other_id not in self.connections:
      self.connections.append(other_id)

  def disconnect(self, other_id: int) -> None:
    """Remove other_id from connections."""
    if other_id in self.connections:
      self.connections.remove(other_id)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


# ── Component dataclass ──────────────────────────────────────────────────

@dataclass
class CVCustomData:
  """customData block inside a CircuitVerse component."""
  # Key is intentionally misspelled — matches upstream CircuitVerse API.
  constructorParamaters: list[CtorParam] = field(default_factory=list)
  nodes: dict[str, NodeValue] = field(default_factory=dict)
  values: dict[str, str | int] | None = None
  _sc_dimensions: dict[str, int] | None = None

  def to_dict(self) -> dict[str, Any]:
    d: dict[str, Any] = {
      "constructorParamaters": self.constructorParamaters,
      "nodes": dict(self.nodes),
    }
    if self.values is not None:
      d["values"] = self.values
    if self._sc_dimensions is not None:
      d["_sc_dimensions"] = self._sc_dimensions
    return d


@dataclass
class CompDict:
  """A single CircuitVerse component dict."""
  x: int
  y: int
  objectType: str
  label: str = ""
  direction: str = "RIGHT"
  labelDirection: str = "LEFT"
  propagationDelay: int = 100
  customData: CVCustomData = field(default_factory=CVCustomData)

  @classmethod
  def create(cls, cv_type: str, x: int, y: int,
             ctor_params: list[CtorParam], nodes: dict[str, NodeValue],
             propagation_delay: int = 100, direction: str = "RIGHT",
             label: str = "") -> CompDict:
    """Factory — replaces _make_comp() from emit.py."""
    return cls(
      x=x, y=y, objectType=cv_type, label=label,
      direction=direction,
      labelDirection=_LABEL_DIR.get(direction, "LEFT"),
      propagationDelay=propagation_delay,
      customData=CVCustomData(
        constructorParamaters=ctor_params, nodes=nodes),
    )

  @classmethod
  def from_dict(cls, d: dict[str, Any]) -> CompDict:
    """Deserialize from a plain dict (for scope_cache JSON loads)."""
    cd = d.get("customData", {})
    return cls(
      x=d["x"], y=d["y"], objectType=d.get("objectType", ""),
      label=d.get("label", ""), direction=d.get("direction", "RIGHT"),
      labelDirection=d.get("labelDirection", "LEFT"),
      propagationDelay=d.get("propagationDelay", 100),
      customData=CVCustomData(
        constructorParamaters=cd.get("constructorParamaters", []),
        nodes=cd.get("nodes", {}),
        values=cd.get("values"),
        _sc_dimensions=cd.get("_sc_dimensions")),
    )

  def to_dict(self) -> dict[str, Any]:
    return {
      "x": self.x, "y": self.y,
      "objectType": self.objectType,
      "label": self.label,
      "direction": self.direction,
      "labelDirection": self.labelDirection,
      "propagationDelay": self.propagationDelay,
      "customData": self.customData.to_dict(),
    }


# ── Remaining type aliases (dynamic-key structures) ──────────────────���───

# components dict: objectType -> [component_dict, ...]
CompMap = dict[str, list[CompDict]]

# bit_nodes: Yosys bit ID -> list of allocated node IDs
BitNodes = dict[int, list[int]]

# Yosys JSON module dict (ymod)
YosysModule = dict[str, Any]

# Absolute positions list: index = node ID, value = (x, y)
AbsPos = list[tuple[int, int]]

# ── Scope dataclass ──────────────────────────────────────────────────────

@dataclass
class VerilogMetadata:
  """verilogMetadata block inside a CircuitVerse scope."""
  isVerilogCircuit: bool = False
  isMainCircuit: bool = False
  code: str = ""
  subCircuitScopeIds: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ScopeDict:
  """A single CircuitVerse scope (circuit/subcircuit)."""
  layout: LayoutDict
  verilogMetadata: VerilogMetadata
  allNodes: list[NodeDict]
  id: int
  name: str
  restrictedCircuitElementsUsed: list[str] = field(default_factory=list)
  nodes: list[int] = field(default_factory=list)
  # Component lists keyed by objectType (Input, Output, Splitter, SubCircuit, ...)
  components: dict[str, list[CompDict | CVSubCircuit]] = field(default_factory=dict)
  # Top-level only
  scopes: list[ScopeDict] | None = None
  logixClipBoardData: bool | None = None
  # Internal (not serialized) — kept for post-export verification
  _abs_pos: AbsPos = field(default_factory=list, repr=False)
  _all_comps: list[CompDict] = field(default_factory=list, repr=False)

  def _rebuild_abs_pos(self) -> None:
    """Reconstruct _abs_pos and _all_comps from loaded scope data."""
    n: int = len(self.allNodes)
    self._abs_pos = [(0, 0)] * n
    self._all_comps = []
    for k, comp_list in self.components.items():
      if k == "SubCircuit":
        continue
      for item in comp_list:
        if not isinstance(item, CompDict):
          continue
        self._all_comps.append(item)
        cx, cy = item.x, item.y
        direction: str = item.direction
        for val in item.customData.nodes.values():
          if isinstance(val, int) and val < n:
            node = self.allNodes[val]
            nx: int = -node.x if direction == "LEFT" else node.x
            self._abs_pos[val] = (cx + nx, cy + node.y)
          elif isinstance(val, list):
            for nid in val:
              if isinstance(nid, int) and nid < n:
                node = self.allNodes[nid]
                nx = -node.x if direction == "LEFT" else node.x
                self._abs_pos[nid] = (cx + nx, cy + node.y)
    # Type-2 bend nodes: abs pos == their (x, y)
    for i, node in enumerate(self.allNodes):
      if node.type == 2:
        self._abs_pos[i] = (node.x, node.y)
    # SubCircuit pin nodes
    for sc in self.components.get("SubCircuit", []):
      if not isinstance(sc, dict):
        continue
      sx, sy = sc.get("x", 0), sc.get("y", 0)
      for nid in sc.get("inputNodes", []) + sc.get("outputNodes", []):
        if isinstance(nid, int) and nid < n:
          self._abs_pos[nid] = (sx + self.allNodes[nid].x, sy + self.allNodes[nid].y)

  def verify_routing(self) -> int:
    """Run routing verification on this scope and all child scopes.

    Returns total number of issues found.
    """
    from verification.verify import verify_routing as _verify
    issues: int = 0
    if not self._abs_pos:
      self._rebuild_abs_pos()
    if self._abs_pos:
      issues += _verify(self.allNodes, self._abs_pos, self._all_comps or None)
    for child in (self.scopes or []):
      issues += child.verify_routing()
    return issues

  @staticmethod
  def _ser_item(item: CompDict | CVSubCircuit) -> dict[str, Any]:
    """Serialize a component item (CompDict -> dict, or CVSubCircuit passthrough)."""
    return item.to_dict() if isinstance(item, CompDict) else dict(item)

  def to_dict(self) -> dict[str, Any]:
    """Serialize to plain dict for JSON output.

    Flattens components into top-level keys (CircuitVerse format).
    """
    d: dict[str, Any] = {
      "layout": self.layout,
      "verilogMetadata": self.verilogMetadata.to_dict(),
      "allNodes": [n.to_dict() for n in self.allNodes],
      "id": self.id,
      "name": self.name,
    }
    # Flatten component lists as top-level keys
    ser = self._ser_item
    for k, v in self.components.items():
      if v:
        d[k] = [ser(item) for item in v]
    d["restrictedCircuitElementsUsed"] = self.restrictedCircuitElementsUsed
    d["nodes"] = self.nodes
    if self.scopes is not None:
      d["scopes"] = [s.to_dict() for s in self.scopes]
    if self.logixClipBoardData is not None:
      d["logixClipBoardData"] = self.logixClipBoardData
    return d

  @classmethod
  def from_dict(cls, d: dict[str, Any]) -> ScopeDict:
    """Deserialize from a plain dict (for scope_cache JSON loads)."""
    skip = {
      "layout", "verilogMetadata", "allNodes", "id", "name",
      "restrictedCircuitElementsUsed", "nodes", "scopes",
      "logixClipBoardData",
    }
    vm = d.get("verilogMetadata", {})
    components: dict[str, list[CompDict | CVSubCircuit]] = {}
    for k, v in d.items():
      if k not in skip and isinstance(v, list):
        if k == "SubCircuit":
          components[k] = v  # type: ignore[assignment]  # CVSubCircuit dicts
        else:
          components[k] = [CompDict.from_dict(item) if isinstance(item, dict) else item for item in v]
    return cls(
      layout=d.get("layout", {}),
      verilogMetadata=VerilogMetadata(
        isVerilogCircuit=vm.get("isVerilogCircuit", False),
        isMainCircuit=vm.get("isMainCircuit", False),
        code=vm.get("code", ""),
        subCircuitScopeIds=vm.get("subCircuitScopeIds", []),
      ),
      allNodes=[NodeDict(**n) if isinstance(n, dict) else n for n in d.get("allNodes", [])],
      id=d.get("id", 0),
      name=d.get("name", ""),
      restrictedCircuitElementsUsed=d.get("restrictedCircuitElementsUsed", []),
      nodes=d.get("nodes", []),
      components=components,
      scopes=[cls.from_dict(s) for s in d.get("scopes", [])] if d.get("scopes") else None,
      logixClipBoardData=d.get("logixClipBoardData"),
    )

# Entity key used in splitter_pass producers/consumers
EntityKey = tuple[str, str]

# Producer entry: (entity_key, port_name, port_bits)
ProducerEntry = tuple[EntityKey, str, list[int]]
