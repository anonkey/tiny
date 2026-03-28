"""Component registry: loads components_reference.json and provides pin position
and dimension lookups for CircuitVerse component types."""

from __future__ import annotations

import json
import os
from typing import Any

_REF_PATH: str = os.path.join(os.path.dirname(__file__), "components_reference.json")
with open(_REF_PATH) as _f:
  _REF: dict[str, Any] = json.load(_f)

# Flatten category -> component into a single dict keyed by component type name
_COMPONENTS: dict[str, Any] = {}
for _cat_key, _cat_val in _REF.items():
  if _cat_key.startswith("_"):
    continue
  if isinstance(_cat_val, dict):
    for _comp_name, _comp_data in _cat_val.items():
      _COMPONENTS[_comp_name] = _comp_data

# Gates with inverted output (bubble) — output at x=25 instead of x=20
_INVERTED_GATES: set[str] = {"NandGate", "NorGate", "XnorGate"}


def _resolve_bw(bw_spec: int | str, params: dict[str, Any]) -> int:
  """Resolve a bitWidth spec like 'param:bitWidth' or int."""
  if isinstance(bw_spec, int):
    return bw_spec
  if isinstance(bw_spec, str) and bw_spec.startswith("param:"):
    pname = bw_spec[6:]
    return params.get(pname, 1)
  return 1


# ── Pin position lookup ─────────────────────────────────────────────────

def pin_pos(component_type: str, pin_name: str, index: int | None = None, **params: Any) -> tuple[int, int]:
  """Return (x, y) for a pin on a component.

  Pin positions are always in RIGHT orientation; the node allocator
  mirrors the x axis for LEFT-direction components in abs_pos().

  For multi-pin arrays (like gate inputs), pass index=0, 1, ...
  Keyword params supply constructor values: bitWidth, inputLength,
  controlSignalSize, bitWidthSplit, etc.
  """
  comp = _COMPONENTS.get(component_type)
  if comp is None:
    raise KeyError(f"Unknown component: {component_type}")

  pins = comp.get("pins", {})
  pin = pins.get(pin_name)
  if pin is None:
    raise KeyError(f"Unknown pin '{pin_name}' on {component_type}")

  # Static pin with x/y
  if "x" in pin and "y" in pin:
    return (pin["x"], pin["y"])

  # IO scaling: Input, Output, ConstantVal — pin at (bitWidth * 10, 0)
  if "position_formula" in pin:
    formula = pin["position_formula"]
    if component_type in ("Input", "Output", "ConstantVal"):
      bw = params.get("bitWidth", 1)
      return (bw * 10, 0)
    # Mux/Demux/Decoder: evaluate shared formula
    if component_type == "Multiplexer":
      return _mux_pin(pin_name, index, **params)
    if component_type == "Demultiplexer":
      return _demux_pin(pin_name, index, **params)
    if component_type == "Decoder":
      return _decoder_pin(pin_name, index, **params)

  # Multi-pin arrays (gate inputs, mux inputs, etc.)
  if "positions_formula" in pin:
    if component_type in ("AndGate", "OrGate", "NandGate", "NorGate",
                          "XorGate", "XnorGate"):
      return _gate_input_pos(pin_name, index, **params)
    if component_type == "Multiplexer":
      return _mux_pin(pin_name, index, **params)
    if component_type == "Demultiplexer":
      return _demux_pin(pin_name, index, **params)
    if component_type == "Decoder":
      return _decoder_pin(pin_name, index, **params)

  # Splitter — dynamic based on bitWidthSplit
  if component_type == "Splitter":
    return _splitter_pin(pin_name, index, **params)

  # Fallback
  return (pin.get("x", 0), pin.get("y", 0))


def _gate_input_pos(pin_name: str, index: int | None, **params: Any) -> tuple[int, int]:
  """Gate input distribution: inputs at x=-10, vertically centered."""
  if pin_name == "output1":
    return (20, 0)  # overridden below for inverted gates
  n = params.get("inputLength", 2)
  if index is None:
    index = 0
  y = -10 * (n - 1) + index * 20
  return (-10, y)


def gate_output_pos(component_type: str) -> tuple[int, int]:
  """Return output pin position for a gate type."""
  if component_type in _INVERTED_GATES:
    return (25, 0)
  return (20, 0)


def _mux_pin(pin_name: str, index: int | None, **params: Any) -> tuple[int, int]:
  """Multiplexer pin positions from shared formula."""
  css = params.get("controlSignalSize", 1)
  input_size = 2 ** css
  x_off = 10 if css == 1 else 0
  y_off = 2 if css <= 3 else 1
  if pin_name == "inp":
    if index is None:
      index = 0
    return (-20 + x_off, int(y_off * 10 * (index - input_size / 2) + 10))
  if pin_name == "output1":
    return (20 - x_off, 0)
  if pin_name == "controlSignalInput":
    return (0, int(y_off * 10 * (input_size / 2 - 1) + x_off + 10))
  return (0, 0)


def _demux_pin(pin_name: str, index: int | None, **params: Any) -> tuple[int, int]:
  """Demultiplexer pin positions from shared formula."""
  css = params.get("controlSignalSize", 1)
  output_size = 2 ** css
  x_off = 10 if css == 1 else 0
  y_off = 2 if css <= 3 else 1
  if pin_name == "input":
    return (20 - x_off, 0)
  if pin_name == "output1":
    if index is None:
      index = 0
    return (-20 + x_off, int(y_off * 10 * (index - output_size / 2) + 10))
  if pin_name == "controlSignalInput":
    return (0, int(y_off * 10 * (output_size / 2 - 1) + x_off + 10))
  return (0, 0)


def _decoder_pin(pin_name: str, index: int | None, **params: Any) -> tuple[int, int]:
  """Decoder pin positions from shared formula."""
  bw = params.get("bitWidth", 1)
  output_size = 2 ** bw
  x_off = 10 if bw == 1 else 0
  y_off = 2 if bw <= 3 else 1
  if pin_name == "input":
    return (20 - x_off, 0)
  if pin_name == "output1":
    if index is None:
      index = 0
    return (-20 + x_off, int(y_off * 10 * (index - output_size / 2) + 10))
  return (0, 0)


def _splitter_pin(pin_name: str, index: int | None, **params: Any) -> tuple[int, int]:
  """Splitter pin positions based on bitWidthSplit."""
  bws = params.get("bitWidthSplit", [1])
  bw = params.get("bitWidth", sum(bws))
  n = len(bws)
  y_offset = int((n / 2 - 1) * 20)
  if pin_name == "inp1":
    return (-10, int(10 + y_offset))
  if pin_name == "outputs":
    if index is None:
      index = 0
    return (20, int(index * 20 - y_offset - 20))
  return (0, 0)


# ── Dimensions lookup ────────────────────────────────────────────────────

def dimensions(component_type: str, **params: Any) -> dict[str, int]:
  """Return {left, right, up, down} for a component."""
  comp = _COMPONENTS.get(component_type)
  if comp is None:
    raise KeyError(f"Unknown component: {component_type}")

  # Static dimensions
  if "dimensions" in comp:
    return dict(comp["dimensions"])

  # Dynamic dimensions
  if "dimensions_formula" in comp:
    return _eval_dimensions(component_type, comp["dimensions_formula"], **params)

  raise ValueError(f"No dimensions found for component type '{component_type}'")


def _eval_dimensions(component_type: str, formula: dict[str, Any], **params: Any) -> dict[str, int]:
  """Evaluate dynamic dimension formulas."""
  # TODO: check if multigate hlsynth
  # Gates: height scales with inputLength
  if component_type in ("AndGate", "OrGate", "NandGate", "NorGate",
                        "XorGate", "XnorGate"):
    n = params.get("inputLength", 2)
    half_h = max(20, n * 10)
    return {"left": 15, "right": 15, "up": half_h, "down": half_h}

  # Mux/Demux/Decoder shared formula
  if component_type in ("Multiplexer", "Demultiplexer"):
    css = params.get("controlSignalSize", 1)
    count = 2 ** css
    x_off = 10 if css == 1 else 0
    y_off = 2 if css <= 3 else 1
    half_h = y_off * 5 * count
    return {"left": 20 - x_off, "right": 20 - x_off, "up": half_h, "down": half_h}

  if component_type == "Decoder":
    bw = params.get("bitWidth", 1)
    count = 2 ** bw
    x_off = 10 if bw == 1 else 0
    y_off = 2 if bw <= 3 else 1
    half_h = y_off * 5 * count
    return {"left": 20 - x_off, "right": 20 - x_off, "up": half_h, "down": half_h}

  # IO components: width scales with bitWidth
  if component_type in ("Input", "Output", "ConstantVal"):
    bw = params.get("bitWidth", 1)
    return {"left": bw * 10, "right": bw * 10, "up": 10, "down": 10}

  # Splitter
  if component_type == "Splitter":
    bws = params.get("bitWidthSplit", [1])
    n = len(bws)
    half_h = (n - 1) * 10 + 10
    return {"left": 10, "right": 10, "up": half_h, "down": half_h}

  # PriorityEncoder
  if component_type == "PriorityEncoder":
    bw = params.get("bitWidth", 1)
    count = 2 ** bw
    y_off = 2 if bw <= 3 else 1
    half_h = y_off * 5 * count + 10
    return {"left": 20, "right": 20, "up": half_h, "down": half_h}

  # Fallback: try to extract from examples or return defaults
  return {"left": 20, "right": 20, "up": 20, "down": 20}


def component_height(component_type: str, **params: Any) -> int:
  """Total component height = up + down."""
  d = dimensions(component_type, **params)
  return d["up"] + d["down"]


def component_width(component_type: str, **params: Any) -> int:
  """Total component width = left + right."""
  d = dimensions(component_type, **params)
  return d["left"] + d["right"]
