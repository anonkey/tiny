"""Shared type aliases and dataclasses for the verilog_export package."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


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
  constructorParamaters: list[Any] = field(default_factory=list)
  nodes: dict[str, Any] = field(default_factory=dict)
  values: dict[str, Any] | None = None
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
             ctor_params: list[Any], nodes: dict[str, Any],
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
  layout: dict[str, Any]
  verilogMetadata: VerilogMetadata
  allNodes: list[NodeDict]
  id: int
  name: str
  restrictedCircuitElementsUsed: list[Any] = field(default_factory=list)
  nodes: list[int] = field(default_factory=list)
  # Component lists keyed by objectType (Input, Output, Splitter, SubCircuit, ...)
  components: dict[str, list[Any]] = field(default_factory=dict)
  # Top-level only
  scopes: list[ScopeDict] | None = None
  logixClipBoardData: bool | None = None

  @staticmethod
  def _ser_item(item: Any) -> Any:
    """Serialize a component item (CompDict -> dict, or passthrough)."""
    return item.to_dict() if isinstance(item, CompDict) else item

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
    components: dict[str, list[Any]] = {}
    for k, v in d.items():
      if k not in skip and isinstance(v, list):
        components[k] = v
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
