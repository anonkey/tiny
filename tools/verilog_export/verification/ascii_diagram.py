"""ASCII diagram generator for CircuitVerse circuit data.

Reads a CircuitVerse scope dict (the same JSON structure produced by
generate_circuitverse_yosys / generate_circuitverse / generate_circuitverse_yosys_hier)
and renders a best-effort ASCII approximation using Unicode box-drawing characters.
"""


# ── Canvas ────────────────────────────────────────────────────────────────

class _AsciiCanvas:
  """2D character grid."""

  def __init__(self, width, height):
    self.w = width
    self.h = height
    self.grid = [[' '] * width for _ in range(height)]

  def get(self, col, row):
    if 0 <= col < self.w and 0 <= row < self.h:
      return self.grid[row][col]
    return ' '

  def put(self, col, row, char):
    if 0 <= col < self.w and 0 <= row < self.h:
      self.grid[row][col] = char

  def put_text(self, col, row, text):
    for i, ch in enumerate(text):
      c = col + i
      if c >= self.w:
        break
      self.put(c, row, ch)

  def hline(self, c1, c2, row, char='─'):
    for c in range(min(c1, c2), max(c1, c2) + 1):
      existing = self.get(c, row)
      self.put(c, row, _merge_wire(existing, char))

  def vline(self, col, r1, r2, char='│'):
    for r in range(min(r1, r2), max(r1, r2) + 1):
      existing = self.get(col, r)
      self.put(col, r, _merge_wire(existing, char))

  def render(self):
    lines = []
    for row in self.grid:
      lines.append(''.join(row).rstrip())
    # Strip trailing blank lines
    while lines and not lines[-1]:
      lines.pop()
    return '\n'.join(lines) + '\n'


# ── Wire character merging ────────────────────────────────────────────────

_WIRE_H = set('─═')
_WIRE_V = set('│')
_WIRE_ANY = _WIRE_H | _WIRE_V | set('┼├┤┬┴┌┐└┘')


def _merge_wire(existing, new):
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

_COMP_KEYS_SKIP = frozenset([
  'layout', 'verilogMetadata', 'allNodes', 'id', 'name',
  'restrictedCircuitElementsUsed', 'nodes', 'scopes',
  'logixClipBoardData',
])


def _iter_components(scope):
  """Yield (comp_type, comp_dict) for every component in the scope."""
  for key, val in scope.items():
    if key in _COMP_KEYS_SKIP:
      continue
    if isinstance(val, list):
      for comp in val:
        if isinstance(comp, dict) and ('x' in comp or 'objectType' in comp):
          yield key, comp


def _compute_abs_positions(scope):
  """Compute absolute (x, y) for every node from the scope dict."""
  nodes = scope.get('allNodes', [])
  abs_pos = [(0, 0)] * len(nodes)
  assigned = set()

  for comp_type, comp in _iter_components(scope):
    cx, cy = comp.get('x', 0), comp.get('y', 0)
    cd = comp.get('customData', {})
    nd = cd.get('nodes', {})
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


def _compute_bounds(scope):
  """Find bounding box of all components."""
  xs, ys = [], []
  for _, comp in _iter_components(scope):
    xs.append(comp.get('x', 0))
    ys.append(comp.get('y', 0))
  if not xs:
    return 0, 0, 100, 100
  # Add some padding
  return min(xs) - 40, min(ys) - 40, max(xs) + 60, max(ys) + 60


def _choose_scale(scope, max_width=120):
  """Compute scale factors and canvas dimensions."""
  min_x, min_y, max_x, max_y = _compute_bounds(scope)
  span_x = max(max_x - min_x, 1)
  span_y = max(max_y - min_y, 1)

  usable = max_width - 4
  sx = usable / span_x
  # Aspect ratio correction: terminal chars are ~2:1 (height:width)
  sy = sx / 2

  canvas_w = int(span_x * sx) + 4
  canvas_h = int(span_y * sy) + 4

  return sx, sy, canvas_w, canvas_h, min_x, min_y


def _map(cv_x, cv_y, sx, sy, min_x, min_y):
  """Map CircuitVerse coords to canvas (col, row)."""
  return int((cv_x - min_x) * sx) + 2, int((cv_y - min_y) * sy) + 2


# ── Wire drawing ──────────────────────────────────────────────────────────

def _draw_wires(canvas, scope, sx, sy, min_x, min_y):
  """Draw all wire segments between connected nodes."""
  nodes = scope.get('allNodes', [])
  abs_pos = _compute_abs_positions(scope)

  seen = set()
  for i, n in enumerate(nodes):
    for j in n.get('connections', []):
      pair = (min(i, j), max(i, j))
      if pair in seen:
        continue
      seen.add(pair)

      ax, ay = abs_pos[i]
      bx, by = abs_pos[j]
      bw = n.get('bitWidth', 1)
      h_char = '═' if bw > 1 else '─'

      c1, r1 = _map(ax, ay, sx, sy, min_x, min_y)
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
          corner = '┐' if r2 > r1 else '┘'
        else:
          corner = '┌' if r2 > r1 else '└'
        canvas.put(c2, r1, corner)


# ── Component drawing ─────────────────────────────────────────────────────

_TYPE_LABELS = {
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
_DEFAULT_EXTENT = (15, 15, 15, 15)  # left, right, up, down


def _comp_extents(comp, comp_type):
  """Return (left, right, up, down) in CV coordinates for a component."""
  # Use constructor params to estimate if available
  cd = comp.get('customData', {})
  cp = cd.get('constructorParamaters', [])

  if comp_type in ('Input', 'Output', 'ConstantVal'):
    bw = 1
    if len(cp) >= 2:
      try:
        bw = int(cp[1])
      except (ValueError, TypeError):
        pass
    return (bw * 10, bw * 10, 10, 10)

  if comp_type in ('AndGate', 'OrGate', 'NandGate', 'NorGate',
                    'XorGate', 'XnorGate'):
    n_inp = 2
    if len(cp) >= 2:
      try:
        n_inp = int(cp[1])
      except (ValueError, TypeError):
        pass
    half_h = max(20, n_inp * 10)
    return (15, 15, half_h, half_h)

  if comp_type == 'NotGate':
    return (10, 25, 10, 10)

  if comp_type in ('Multiplexer', 'Demultiplexer'):
    css = 1
    if len(cp) >= 2:
      try:
        css = int(cp[1])
      except (ValueError, TypeError):
        pass
    count = 2 ** css
    half_h = max(20, count * 10)
    return (20, 20, half_h, half_h)

  if comp_type == 'DflipFlop':
    return (20, 20, 20, 20)

  if comp_type == 'Adder':
    return (20, 30, 20, 20)

  if comp_type == 'Splitter':
    return (10, 10, 10, 10)

  return _DEFAULT_EXTENT


def _draw_box(canvas, c1, r1, c2, r2, label=''):
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
  inner_w = c2 - c1 - 1
  if label and inner_w > 0:
    shown = label[:inner_w]
    mid_r = (r1 + r2) // 2
    pad = (inner_w - len(shown)) // 2
    canvas.put_text(c1 + 1 + pad, mid_r, shown)


def _draw_components(canvas, scope, sx, sy, min_x, min_y):
  """Draw all components as labeled boxes or compact markers."""
  for comp_type, comp in _iter_components(scope):
    cx, cy = comp.get('x', 0), comp.get('y', 0)
    col, row = _map(cx, cy, sx, sy, min_x, min_y)

    if comp_type == 'Splitter':
      # Render splitters as small markers — skip if too crowded
      canvas.put(col, row, '·')
      continue

    label = comp.get('label', '')
    type_label = _TYPE_LABELS.get(comp_type, comp_type[:4])

    if comp_type == 'Input':
      display = f'▷{label or "in"}'
      canvas.put_text(col, row, display)
      continue

    if comp_type == 'Output':
      display = f'{label or "out"}▷'
      canvas.put_text(col, row, display)
      continue

    if comp_type == 'ConstantVal':
      cd = comp.get('customData', {})
      cp = cd.get('constructorParamaters', [])
      val = cp[2] if len(cp) >= 3 else '?'
      canvas.put_text(col, row, str(val))
      continue

    # SubCircuit (no objectType field, has 'id' key)
    if 'id' in comp and 'objectType' not in comp:
      comp_type = 'SubCircuit'
      type_label = label or 'SC'

    # Draw as box
    left, right, up, down = _comp_extents(comp, comp_type)
    c1, r1 = _map(cx - left, cy - up, sx, sy, min_x, min_y)
    c2, r2 = _map(cx + right, cy + down, sx, sy, min_x, min_y)

    # Use label if available, otherwise type abbreviation
    box_label = label if label else type_label
    _draw_box(canvas, c1, r1, c2, r2, box_label)


# ── Title ─────────────────────────────────────────────────────────────────

def _draw_title(canvas, scope):
  """Draw the circuit name at the top."""
  name = scope.get('name', '')
  if name:
    canvas.put_text(2, 0, f'[ {name} ]')


# ── Public API ────────────────────────────────────────────────────────────

def generate_ascii_diagram(scope, max_width=120):
  """Generate an ASCII diagram from a CircuitVerse scope dict.

  scope: The top-level CircuitVerse JSON dict (same structure
         returned by generate_circuitverse_yosys, etc.).
  max_width: Maximum diagram width in characters.

  Returns the ASCII diagram as a string.
  """
  # Check for empty circuit
  has_comps = any(True for _ in _iter_components(scope))
  if not has_comps:
    name = scope.get('name', 'circuit')
    return f'[ {name} ] (no components)\n'

  sx, sy, canvas_w, canvas_h, min_x, min_y = _choose_scale(scope, max_width)

  canvas = _AsciiCanvas(canvas_w, canvas_h)

  # Draw wires first (components overwrite on top)
  _draw_wires(canvas, scope, sx, sy, min_x, min_y)

  # Draw components on top of wires
  _draw_components(canvas, scope, sx, sy, min_x, min_y)

  # Title
  _draw_title(canvas, scope)

  return canvas.render()
