"""ASCII diagram generator for CircuitVerse circuit data.

Reads a CircuitVerse scope dict (the same JSON structure produced by
generate_circuitverse_yosys / generate_circuitverse / generate_circuitverse_yosys_hier)
and renders a best-effort ASCII approximation using Unicode box-drawing characters.
"""
from __future__ import annotations

from typing import Any, Iterator

from common.types import ScopeDict, AbsPos


# ── Canvas ────────────────────────────────────────────────────────────────

class _AsciiCanvas:
  """2D character grid."""

  w: int
  h: int
  grid: list[list[str]]

  def __init__(self, width: int, height: int) -> None:
    self.w = width
    self.h = height
    self.grid = [[' '] * width for _ in range(height)]

  def get(self, col: int, row: int) -> str:
    if 0 <= col < self.w and 0 <= row < self.h:
      return self.grid[row][col]
    return ' '

  def put(self, col: int, row: int, char: str) -> None:
    if 0 <= col < self.w and 0 <= row < self.h:
      self.grid[row][col] = char

  def put_text(self, col: int, row: int, text: str) -> None:
    for i, ch in enumerate(text):
      c = col + i
      if c >= self.w:
        break
      self.put(c, row, ch)

  def hline(self, c1: int, c2: int, row: int, char: str = '─') -> None:
    for c in range(min(c1, c2), max(c1, c2) + 1):
      existing = self.get(c, row)
      self.put(c, row, _merge_wire(existing, char))

  def vline(self, col: int, r1: int, r2: int, char: str = '│') -> None:
    for r in range(min(r1, r2), max(r1, r2) + 1):
      existing = self.get(col, r)
      self.put(col, r, _merge_wire(existing, char))

  def render(self) -> str:
    lines: list[str] = []
    for row in self.grid:
      lines.append(''.join(row).rstrip())
    # Strip trailing blank lines
    while lines and not lines[-1]:
      lines.pop()
    return '\n'.join(lines) + '\n'


# ── Wire character merging ────────────────────────────────────────────────

_WIRE_H: set[str] = set('─═')
_WIRE_V: set[str] = set('│')
_WIRE_ANY: set[str] = _WIRE_H | _WIRE_V | set('┼├┤┬┴┌┐└┘')


def _merge_wire(existing: str, new: str) -> str:
  if existing == ' ':
    return new
  if existing == new:
    return existing
  h = {existing, new}
  # Crossing
  if existing in _WIRE_V and new in _WIRE_H:
    return '┼'
  if existing in _WIRE_H and new in _WIRE_V:
    return '┼'
  # T-junctions
  if existing == '─' and new == '┌':
    return '┬'
  if existing == '─' and new == '┐':
    return '┬'
  if existing == '─' and new == '└':
    return '┴'
  if existing == '─' and new == '┘':
    return '┴'
  if existing == '│' and new == '┌':
    return '├'
  if existing == '│' and new == '└':
    return '├'
  if existing == '│' and new == '┐':
    return '┤'
  if existing == '│' and new == '┘':
    return '┤'
  # If already a junction, keep it
  if existing in '┼├┤┬┴':
    return existing
  return new


# ── Coordinate helpers ────────────────────────────────────────────────────

_COMP_KEYS_SKIP: frozenset[str] = frozenset([
  'layout', 'verilogMetadata', 'allNodes', 'id', 'name',
  'restrictedCircuitElementsUsed', 'nodes', 'scopes',
  'logixClipBoardData',
])


def _iter_components(scope: ScopeDict) -> Iterator[tuple[str, dict[str, Any]]]:
  """Yield (comp_type, comp_dict) for every component in the scope."""
  for key, val in scope.items():
    if key in _COMP_KEYS_SKIP:
      continue
    if isinstance(val, list):
      for comp in val:
        if isinstance(comp, dict) and ('x' in comp or 'objectType' in comp):
          yield key, comp


def _compute_abs_positions(scope: ScopeDict) -> AbsPos:
  """Compute absolute (x, y) for every node from the scope dict."""
  nodes: list[dict[str, Any]] = scope.get('allNodes', [])
  abs_pos: AbsPos = [(0, 0)] * len(nodes)
  assigned: set[int] = set()

  for comp_type, comp in _iter_components(scope):
    cx: int = comp.get('x', 0)
    cy: int = comp.get('y', 0)
    cd: dict[str, Any] = comp.get('customData', {})
    nd: dict[str, Any] = cd.get('nodes', {})
    for val in nd.values():
      if isinstance(val, int) and 0 <= val < len(nodes):
        abs_pos[val] = (cx + nodes[val]['x'], cy + nodes[val]['y'])
        assigned.add(val)
      elif isinstance(val, list):
        for nid in val:
          if isinstance(nid, int) and 0 <= nid < len(nodes):
            abs_pos[nid] = (cx + nodes[nid]['x'], cy + nodes[nid]['y'])
            assigned.add(nid)
    # SubCircuit inputNodes/outputNodes
    for key in ('inputNodes', 'outputNodes'):
      for nid in comp.get(key, []):
        if isinstance(nid, int) and 0 <= nid < len(nodes):
          abs_pos[nid] = (cx + nodes[nid]['x'], cy + nodes[nid]['y'])
          assigned.add(nid)

  # Bend nodes (type 2) store absolute coords directly
  for i, n in enumerate(nodes):
    if i not in assigned and n.get('type') == 2:
      abs_pos[i] = (n['x'], n['y'])

  return abs_pos


def _compute_bounds(scope: ScopeDict) -> tuple[int, int, int, int]:
  """Find bounding box of all components."""
  xs: list[int] = []
  ys: list[int] = []
  for _, comp in _iter_components(scope):
    xs.append(comp.get('x', 0))
    ys.append(comp.get('y', 0))
  if not xs:
    return 0, 0, 100, 100
  # Add some padding
  return min(xs) - 40, min(ys) - 40, max(xs) + 60, max(ys) + 60


def _choose_scale(scope: ScopeDict, max_width: int = 120) -> tuple[float, float, int, int, int, int]:
  """Compute scale factors and canvas dimensions."""
  min_x: int
  min_y: int
  max_x: int
  max_y: int
  min_x, min_y, max_x, max_y = _compute_bounds(scope)
  span_x: int = max(max_x - min_x, 1)
  span_y: int = max(max_y - min_y, 1)

  usable: int = max_width - 4
  sx: float = usable / span_x
  # Aspect ratio correction: terminal chars are ~2:1 (height:width)
  sy: float = sx / 2

  canvas_w: int = int(span_x * sx) + 4
  canvas_h: int = int(span_y * sy) + 4

  return sx, sy, canvas_w, canvas_h, min_x, min_y


def _map(cv_x: int, cv_y: int, sx: float, sy: float, min_x: int, min_y: int) -> tuple[int, int]:
  """Map CircuitVerse coords to canvas (col, row)."""
  return int((cv_x - min_x) * sx) + 2, int((cv_y - min_y) * sy) + 2


# ── Wire drawing ──────────────────────────────────────────────────────────

def _draw_wires(canvas: _AsciiCanvas, scope: ScopeDict, sx: float, sy: float, min_x: int, min_y: int) -> None:
  """Draw all wire segments between connected nodes."""
  nodes: list[dict[str, Any]] = scope.get('allNodes', [])
  abs_pos: AbsPos = _compute_abs_positions(scope)

  seen: set[tuple[int, int]] = set()
  for i, n in enumerate(nodes):
    for j in n.get('connections', []):
      pair: tuple[int, int] = (min(i, j), max(i, j))
      if pair in seen:
        continue
      seen.add(pair)

      ax: int
      ay: int
      ax, ay = abs_pos[i]
      bx: int
      by: int
      bx, by = abs_pos[j]
      bw: int = n.get('bitWidth', 1)
      h_char: str = '═' if bw > 1 else '─'

      c1: int
      r1: int
      c1, r1 = _map(ax, ay, sx, sy, min_x, min_y)
      c2: int
      r2: int
      c2, r2 = _map(bx, by, sx, sy, min_x, min_y)

      if r1 == r2:
        # Horizontal segment
        canvas.hline(c1, c2, r1, h_char)
      elif c1 == c2:
        # Vertical segment
        canvas.vline(c1, r1, r2)
      else:
        # L-bend: horizontal first, then vertical
        canvas.hline(c1, c2, r1, h_char)
        canvas.vline(c2, r1, r2)
        # Corner character
        if c2 > c1:
          corner: str = '┐' if r2 > r1 else '┘'
        else:
          corner = '┌' if r2 > r1 else '└'
        canvas.put(c2, r1, corner)


# ── Component drawing ─────────────────────────────────────────────────────

_TYPE_LABELS: dict[str, str] = {
  'AndGate': 'AND', 'OrGate': 'OR', 'NandGate': 'NAND',
  'NorGate': 'NOR', 'XorGate': 'XOR', 'XnorGate': 'XNOR',
  'NotGate': 'NOT', 'Buffer': 'BUF',
  'Multiplexer': 'MUX', 'Demultiplexer': 'DMUX',
  'DflipFlop': 'DFF', 'Adder': 'ADD', 'Subtractor': 'SUB',
  'Multiplier': 'MUL', 'Divider': 'DIV',
  'ALU': 'ALU', 'Decoder': 'DEC',
  'PriorityEncoder': 'ENC',
}

# Component dimension estimates (half-extents) for types without registry
_DEFAULT_EXTENT: tuple[int, int, int, int] = (15, 15, 15, 15)  # left, right, up, down


def _comp_extents(comp: dict[str, Any], comp_type: str) -> tuple[int, int, int, int]:
  """Return (left, right, up, down) in CV coordinates for a component."""
  # Use constructor params to estimate if available
  cd: dict[str, Any] = comp.get('customData', {})
  cp: list[Any] = cd.get('constructorParamaters', [])

  if comp_type in ('Input', 'Output', 'ConstantVal'):
    bw: int = 1
    if len(cp) >= 2:
      try:
        bw = int(cp[1])
      except (ValueError, TypeError):
        pass
    return (bw * 10, bw * 10, 10, 10)

  if comp_type in ('AndGate', 'OrGate', 'NandGate', 'NorGate',
                    'XorGate', 'XnorGate'):
    n_inp: int = 2
    if len(cp) >= 2:
      try:
        n_inp = int(cp[1])
      except (ValueError, TypeError):
        pass
    half_h: int = max(20, n_inp * 10)
    return (15, 15, half_h, half_h)

  if comp_type == 'NotGate':
    return (10, 25, 10, 10)

  if comp_type in ('Multiplexer', 'Demultiplexer'):
    css: int = 1
    if len(cp) >= 2:
      try:
        css = int(cp[1])
      except (ValueError, TypeError):
        pass
    count: int = 2 ** css
    half_h = max(20, count * 10)
    return (20, 20, half_h, half_h)

  if comp_type == 'DflipFlop':
    return (20, 20, 20, 20)

  if comp_type == 'Adder':
    return (20, 30, 20, 20)

  if comp_type == 'Splitter':
    return (10, 10, 10, 10)

  return _DEFAULT_EXTENT


def _draw_box(canvas: _AsciiCanvas, c1: int, r1: int, c2: int, r2: int, label: str = '') -> None:
  """Draw a Unicode box with optional centered label."""
  # Clamp to at least 2 wide, 2 tall
  if c2 - c1 < 2:
    c2 = c1 + 2
  if r2 - r1 < 2:
    r2 = r1 + 2

  canvas.put(c1, r1, '┌')
  canvas.put(c2, r1, '┐')
  canvas.put(c1, r2, '└')
  canvas.put(c2, r2, '┘')

  for c in range(c1 + 1, c2):
    canvas.put(c, r1, '─')
    canvas.put(c, r2, '─')
  for r in range(r1 + 1, r2):
    canvas.put(c1, r, '│')
    canvas.put(c2, r, '│')

  # Fill interior with spaces (overwrite wires)
  for r in range(r1 + 1, r2):
    for c in range(c1 + 1, c2):
      canvas.put(c, r, ' ')

  # Center label
  inner_w: int = c2 - c1 - 1
  if label and inner_w > 0:
    shown: str = label[:inner_w]
    mid_r: int = (r1 + r2) // 2
    pad: int = (inner_w - len(shown)) // 2
    canvas.put_text(c1 + 1 + pad, mid_r, shown)


def _draw_components(canvas: _AsciiCanvas, scope: ScopeDict, sx: float, sy: float, min_x: int, min_y: int) -> None:
  """Draw all components as labeled boxes or compact markers."""
  for comp_type, comp in _iter_components(scope):
    cx: int = comp.get('x', 0)
    cy: int = comp.get('y', 0)
    col: int
    row: int
    col, row = _map(cx, cy, sx, sy, min_x, min_y)

    if comp_type == 'Splitter':
      # Render splitters as small markers — skip if too crowded
      canvas.put(col, row, '·')
      continue

    label: str = comp.get('label', '')
    type_label: str = _TYPE_LABELS.get(comp_type, comp_type[:4])

    if comp_type == 'Input':
      display: str = f'▷{label or "in"}'
      canvas.put_text(col, row, display)
      continue

    if comp_type == 'Output':
      display = f'{label or "out"}▷'
      canvas.put_text(col, row, display)
      continue

    if comp_type == 'ConstantVal':
      cd: dict[str, Any] = comp.get('customData', {})
      cp: list[Any] = cd.get('constructorParamaters', [])
      val: Any = cp[2] if len(cp) >= 3 else '?'
      canvas.put_text(col, row, str(val))
      continue

    # SubCircuit (no objectType field, has 'id' key)
    if 'id' in comp and 'objectType' not in comp:
      comp_type = 'SubCircuit'
      type_label = label or 'SC'

    # Draw as box
    left: int
    right: int
    up: int
    down: int
    left, right, up, down = _comp_extents(comp, comp_type)
    c1: int
    r1: int
    c1, r1 = _map(cx - left, cy - up, sx, sy, min_x, min_y)
    c2: int
    r2: int
    c2, r2 = _map(cx + right, cy + down, sx, sy, min_x, min_y)

    # Use label if available, otherwise type abbreviation
    box_label: str = label if label else type_label
    _draw_box(canvas, c1, r1, c2, r2, box_label)


# ── Title ─────────────────────────────────────────────────────────────────

def _draw_title(canvas: _AsciiCanvas, scope: ScopeDict) -> None:
  """Draw the circuit name at the top."""
  name: str = scope.get('name', '')
  if name:
    canvas.put_text(2, 0, f'[ {name} ]')


# ── Public API ────────────────────────────────────────────────────────────

def generate_ascii_diagram(scope: ScopeDict, max_width: int = 120) -> str:
  """Generate an ASCII diagram from a CircuitVerse scope dict.

  scope: The top-level CircuitVerse JSON dict (same structure
         returned by generate_circuitverse_yosys, etc.).
  max_width: Maximum diagram width in characters.

  Returns the ASCII diagram as a string.
  """
  # Check for empty circuit
  has_comps: bool = any(True for _ in _iter_components(scope))
  if not has_comps:
    name: str = scope.get('name', 'circuit')
    return f'[ {name} ] (no components)\n'

  sx: float
  sy: float
  canvas_w: int
  canvas_h: int
  min_x: int
  min_y: int
  sx, sy, canvas_w, canvas_h, min_x, min_y = _choose_scale(scope, max_width)

  canvas: _AsciiCanvas = _AsciiCanvas(canvas_w, canvas_h)

  # Draw wires first (components overwrite on top)
  _draw_wires(canvas, scope, sx, sy, min_x, min_y)

  # Draw components on top of wires
  _draw_components(canvas, scope, sx, sy, min_x, min_y)

  # Title
  _draw_title(canvas, scope)

  return canvas.render()
