#!/usr/bin/env python3
"""Export Verilog modules to various schematic formats.

Parses module headers (ports, parameters, submodule instantiations) and
exports to KiCad (.kicad_sch / .kicad_sym) or DigitalJS JSON (CircuitVerse
compatible).

Usage:
    python verilog_export.py alu                              # KiCad flat (default)
    python verilog_export.py half_cpu --format kicad-hier     # KiCad hierarchical
    python verilog_export.py half_cpu --format kicad-sym      # KiCad symbols only
    python verilog_export.py half_cpu --format digitaljs      # DigitalJS / CircuitVerse
    python verilog_export.py half_cpu -o out/                 # custom output directory
"""

import argparse
import json
import os
import re
import sys
import uuid as _uuid

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_MANAGER_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), "manager")
if _MANAGER_DIR not in sys.path:
    sys.path.insert(0, _MANAGER_DIR)

from manager_utils import discover_modules, find_project_root, resolve_deps


# ---------------------------------------------------------------------------
#  Verilog parser
# ---------------------------------------------------------------------------

class Port:
    __slots__ = ("name", "direction", "width", "msb", "lsb", "raw_range")

    def __init__(self, name, direction, width=1, msb=0, lsb=0, raw_range=""):
        self.name = name
        self.direction = direction  # "input" | "output"
        self.width = width
        self.msb = msb
        self.lsb = lsb
        self.raw_range = raw_range  # e.g. "[7:0]" or "[N-1:0]"

    def label(self):
        if self.width > 1 or self.raw_range:
            rng = self.raw_range or f"[{self.msb}:{self.lsb}]"
            return f"{self.name}{rng}"
        return self.name


class Param:
    __slots__ = ("name", "default")

    def __init__(self, name, default=""):
        self.name = name
        self.default = default


class Instance:
    __slots__ = ("module_name", "inst_name", "params", "connections")

    def __init__(self, module_name, inst_name, params=None, connections=None):
        self.module_name = module_name
        self.inst_name = inst_name
        self.params = params or {}      # {param_name: value_str}
        self.connections = connections or {}  # {port_name: net_expr}


class Module:
    __slots__ = ("name", "params", "ports", "instances", "path")

    def __init__(self, name, params=None, ports=None, instances=None, path=""):
        self.name = name
        self.params = params or []
        self.ports = ports or []
        self.instances = instances or []
        self.path = path

    @property
    def inputs(self):
        return [p for p in self.ports if p.direction == "input"]

    @property
    def outputs(self):
        return [p for p in self.ports if p.direction == "output"]


def _strip_comments(text):
    """Remove // and /* */ comments."""
    text = re.sub(r'//.*', '', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return text


def _match_balanced_parens(text, start):
    """From position of '(' at `start`, return the index after matching ')'."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _parse_dot_connections(text):
    """Parse '.name(expr)' pairs from a string, handling nested parens."""
    result = {}
    for m in re.finditer(r'\.(\w+)\s*\(', text):
        name = m.group(1)
        paren_start = m.end() - 1
        paren_end = _match_balanced_parens(text, paren_start)
        value = text[paren_start + 1:paren_end - 1].strip()
        result[name] = value
    return result


_INST_SKIP_KW = {
    'module', 'input', 'output', 'wire', 'reg', 'assign',
    'always', 'initial', 'function', 'endfunction', 'generate',
    'endgenerate', 'for', 'if', 'else', 'begin', 'end',
    'localparam', 'parameter', 'genvar', 'integer',
}


def _parse_instances(body):
    """Parse submodule instantiations from a module body, handling nested parens."""
    instances = []
    # Pattern: module_name [#(...)] inst_name (
    # We find candidates by looking for: word [#(...)] word (
    pat = re.compile(r'(\w+)\s*(#\s*\()?')
    pos = 0
    while pos < len(body):
        m = pat.match(body, pos)
        if not m:
            pos += 1
            continue

        mtype = m.group(1)
        if mtype in _INST_SKIP_KW:
            pos = m.end()
            continue

        has_params = m.group(2) is not None

        if has_params:
            # Find matching ')' for the #( block
            param_paren_start = body.index('(', m.start(2))
            param_paren_end = _match_balanced_parens(body, param_paren_start)
            param_str = body[param_paren_start + 1:param_paren_end - 1]
            rest_start = param_paren_end
        else:
            param_str = ""
            rest_start = m.end()

        # After params: expect inst_name then '('
        rest = body[rest_start:].lstrip()
        inst_m = re.match(r'(\w+)\s*\(', rest)
        if not inst_m:
            pos = rest_start + 1
            continue

        iname = inst_m.group(1)
        if iname in _INST_SKIP_KW:
            pos = rest_start + 1
            continue

        conn_paren_start = rest_start + rest.index('(', inst_m.start())
        conn_paren_end = _match_balanced_parens(body, conn_paren_start)
        conn_str = body[conn_paren_start + 1:conn_paren_end - 1]

        # Check for semicolon after
        after = body[conn_paren_end:conn_paren_end + 10].lstrip()
        if not after.startswith(';'):
            pos = conn_paren_end
            continue

        inst_params = _parse_dot_connections(param_str)
        connections = _parse_dot_connections(conn_str)
        instances.append(Instance(mtype, iname, inst_params, connections))

        pos = conn_paren_end + 1

    return instances


def _eval_width(expr, params):
    """Try to evaluate a width expression given parameter defaults."""
    expr = expr.strip()
    if not expr:
        return 1, expr
    # Replace parameter names with defaults
    env = {}
    for p in params:
        try:
            env[p.name] = int(p.default)
        except (ValueError, TypeError):
            pass
    # Handle $clog2
    def clog2_sub(m):
        inner = m.group(1)
        try:
            val = eval(inner, {"__builtins__": {}}, env)
            return str(max(1, (val - 1).bit_length()))
        except Exception:
            return m.group(0)
    expr_eval = re.sub(r'\$clog2\(([^)]+)\)', clog2_sub, expr)
    try:
        val = eval(expr_eval, {"__builtins__": {}}, env)
        return int(val), f"[{expr}]"
    except Exception:
        return 1, f"[{expr}]"


def parse_verilog(filepath):
    """Parse a Verilog file and return a list of Module objects."""
    with open(filepath) as f:
        text = f.read()
    text = _strip_comments(text)
    modules = []

    # Split by module...endmodule
    mod_blocks = re.finditer(
        r'module\s+(\w+)\s*(#\s*\(.*?\))?\s*\((.*?)\)\s*;(.*?)endmodule',
        text, re.DOTALL
    )

    for mb in mod_blocks:
        mod_name = mb.group(1)
        param_block = mb.group(2) or ""
        port_block = mb.group(3) or ""
        body = mb.group(4) or ""

        # --- Parameters ---
        params = []
        # From #(...) header
        for pm in re.finditer(r'parameter\s+(\w+)\s*=\s*([^,\)]+)', param_block):
            params.append(Param(pm.group(1), pm.group(2).strip()))
        # From body (old-style)
        for pm in re.finditer(r'^\s*parameter\s+(\w+)\s*=\s*([^;]+);', body, re.MULTILINE):
            if not any(p.name == pm.group(1) for p in params):
                params.append(Param(pm.group(1), pm.group(2).strip()))

        # --- Ports ---
        ports = []

        # Modern style: direction [range] name in port block
        # Also handle: output wire, output reg, input wire
        modern = re.findall(
            r'(input|output)\s+(?:wire|reg)?\s*(\[[^\]]*\])?\s*(\w+)',
            port_block
        )
        if modern:
            for direction, rng, name in modern:
                if rng:
                    inner = rng.strip("[]")
                    parts = inner.split(":")
                    if len(parts) == 2:
                        width, raw = _eval_width(f"{parts[0]} - {parts[1]} + 1", params)
                        # Try numeric msb:lsb
                        try:
                            msb = int(eval(parts[0].strip(), {"__builtins__": {}},
                                          {p.name: int(p.default) for p in params if p.default.strip().isdigit()}))
                            lsb = int(eval(parts[1].strip(), {"__builtins__": {}},
                                          {p.name: int(p.default) for p in params if p.default.strip().isdigit()}))
                            width = msb - lsb + 1
                        except Exception:
                            pass
                        ports.append(Port(name, direction, width, msb=0, lsb=0, raw_range=rng))
                    else:
                        ports.append(Port(name, direction, 1, raw_range=rng))
                else:
                    ports.append(Port(name, direction, 1))
        else:
            # Old-style: port names in module(...), declarations in body
            port_names = [n.strip() for n in port_block.split(",") if n.strip()]
            # Find declarations in body
            for decl in re.finditer(
                r'(input|output)\s+(?:wire|reg)?\s*(\[[^\]]*\])?\s*([^;]+);',
                body
            ):
                direction = decl.group(1)
                rng = decl.group(2) or ""
                names_str = decl.group(3)
                for name in names_str.split(","):
                    name = name.strip()
                    if not name or name not in port_names:
                        continue
                    if rng:
                        inner = rng.strip("[]")
                        parts = inner.split(":")
                        width = 1
                        if len(parts) == 2:
                            try:
                                env = {p.name: int(p.default) for p in params
                                       if p.default.strip().isdigit()}
                                msb = int(eval(parts[0].strip(), {"__builtins__": {}}, env))
                                lsb = int(eval(parts[1].strip(), {"__builtins__": {}}, env))
                                width = msb - lsb + 1
                            except Exception:
                                pass
                        ports.append(Port(name, direction, width, raw_range=rng))
                    else:
                        ports.append(Port(name, direction, 1))

        # --- Submodule instances ---
        instances = []
        instances = _parse_instances(body)

        modules.append(Module(mod_name, params, ports, instances, filepath))

    return modules


# ---------------------------------------------------------------------------
#  UUID helper
# ---------------------------------------------------------------------------

_uuid_counter = 0

def _uuid():
    global _uuid_counter
    _uuid_counter += 1
    return f"{_uuid_counter:08x}-0000-0000-0000-{_uuid_counter:012x}"


# ---------------------------------------------------------------------------
#  KiCad symbol generation
# ---------------------------------------------------------------------------

# Layout constants (mm)
PIN_LEN = 2.54
PIN_PITCH = 2.54
BOX_PAD_X = 12.7   # half-width of symbol box
FONT_SYM = 1.016
FONT_REF = 1.27

def _shape_for(mod):
    """Decide symbol shape: 'alu' for ALU-like, 'mux' for mux-like, 'rect' default."""
    n = mod.name.lower()
    if "alu" in n and "mux" not in n:
        return "alu"
    if "mux" in n:
        return "mux"
    return "rect"


def _symbol_height(mod):
    n_in = len(mod.inputs)
    n_out = len(mod.outputs)
    n_max = max(n_in, n_out, 1)
    return (n_max + 1) * PIN_PITCH


def generate_symbol(mod, lib_prefix="half_cpu"):
    """Return KiCad symbol S-expression string for a Module."""
    shape = _shape_for(mod)
    half_h = _symbol_height(mod) / 2
    half_w = BOX_PAD_X

    # Value text
    val_text = mod.name
    if mod.params:
        pstr = ", ".join(f"{p.name}={p.default}" for p in mod.params)
        val_text = f"{mod.name} #({pstr})"

    lines = []
    full_name = f"{lib_prefix}:{mod.name}"
    lines.append(f'  (symbol "{full_name}"')
    lines.append(f'    (in_bom no) (on_board no)')
    lines.append(f'    (property "Reference" "U" (at 0 {half_h + 3.81:.2f} 0) (effects (font (size {FONT_REF} {FONT_REF}))))')
    lines.append(f'    (property "Value" "{val_text}" (at 0 {half_h + 1.27:.2f} 0) (effects (font (size {FONT_REF} {FONT_REF}))))')

    # Shape sub-symbol _0_1
    lines.append(f'    (symbol "{mod.name}_0_1"')
    if shape == "alu":
        lines.append(f'      (polyline (pts (xy -{half_w} {half_h:.2f}) (xy {half_w} {half_h * 0.7:.2f}) (xy {half_w} {-half_h * 0.7:.2f}) (xy -{half_w} {-half_h:.2f}) (xy -{half_w} {half_h:.2f}))')
        lines.append(f'        (stroke (width 0.254) (type default)) (fill (type background)))')
    elif shape == "mux":
        lines.append(f'      (polyline (pts (xy -{half_w * 0.6:.2f} {half_h:.2f}) (xy {half_w * 0.6:.2f} {half_h * 0.6:.2f}) (xy {half_w * 0.6:.2f} {-half_h * 0.6:.2f}) (xy -{half_w * 0.6:.2f} {-half_h:.2f}) (xy -{half_w * 0.6:.2f} {half_h:.2f}))')
        lines.append(f'        (stroke (width 0.254) (type default)) (fill (type background)))')
    else:
        lines.append(f'      (rectangle (start -{half_w} {half_h:.2f}) (end {half_w} {-half_h:.2f})')
        lines.append(f'        (stroke (width 0.254) (type default)) (fill (type background)))')
    lines.append(f'    )')

    # Pins sub-symbol _1_1
    lines.append(f'    (symbol "{mod.name}_1_1"')
    pin_num = 1

    # Input pins (left side)
    n_in = len(mod.inputs)
    for i, p in enumerate(mod.inputs):
        y = half_h - PIN_PITCH - i * PIN_PITCH
        lbl = p.label()
        x = -half_w - PIN_LEN
        lines.append(f'      (pin input line (at {x:.2f} {y:.2f} 0) (length {PIN_LEN}) (name "{lbl}" (effects (font (size {FONT_SYM} {FONT_SYM})))) (number "{pin_num}" (effects (font (size {FONT_SYM} {FONT_SYM})))))')
        pin_num += 1

    # Output pins (right side)
    n_out = len(mod.outputs)
    for i, p in enumerate(mod.outputs):
        y = half_h - PIN_PITCH - i * PIN_PITCH
        lbl = p.label()
        x = half_w + PIN_LEN
        lines.append(f'      (pin output line (at {x:.2f} {y:.2f} 180) (length {PIN_LEN}) (name "{lbl}" (effects (font (size {FONT_SYM} {FONT_SYM})))) (number "{pin_num}" (effects (font (size {FONT_SYM} {FONT_SYM})))))')
        pin_num += 1

    lines.append(f'    )')
    lines.append(f'  )')
    return "\n".join(lines), pin_num - 1


def generate_sym_lib(modules, lib_prefix="half_cpu"):
    """Generate a complete .kicad_sym library string for a list of Modules."""
    lines = [
        '(kicad_symbol_lib',
        '  (version 20231120)',
        '  (generator "verilog_export")',
        '  (generator_version "1.0")',
        '',
    ]
    for mod in modules:
        sym, _ = generate_symbol(mod, lib_prefix)
        lines.append(sym)
        lines.append('')
    lines.append(')')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  KiCad schematic generation
# ---------------------------------------------------------------------------

# Placement grid
GRID_X = 76.2   # horizontal spacing between modules
GRID_Y = 0      # same row by default
ORIGIN_X = 50.8
ORIGIN_Y = 76.2

def _place_modules(modules):
    """Compute (x, y) for each module in a left-to-right flow."""
    positions = {}
    x = ORIGIN_X
    for mod in modules:
        h = _symbol_height(mod)
        positions[mod.name] = (x, ORIGIN_Y)
        x += GRID_X + max(0, len(mod.name) - 6) * 2
    return positions


def _emit_lib_symbols(modules, lib_prefix):
    """Emit inline lib_symbols block."""
    lines = ['  (lib_symbols']
    for mod in modules:
        sym, _ = generate_symbol(mod, lib_prefix)
        lines.append(sym)
    lines.append('  )')
    return "\n".join(lines)


def _emit_symbol_instance(mod, pos, ref_num, lib_prefix):
    """Emit a symbol placement."""
    x, y = pos
    n_pins = len(mod.ports)
    lines = []
    lines.append(f'  (symbol')
    lines.append(f'    (lib_id "{lib_prefix}:{mod.name}")')
    lines.append(f'    (at {x:.2f} {y:.2f} 0)')
    lines.append(f'    (unit 1)')
    lines.append(f'    (uuid "{_uuid()}")')
    lines.append(f'    (property "Reference" "U{ref_num}" (at {x:.2f} {y - _symbol_height(mod) / 2 - 5.08:.2f} 0) (effects (font (size {FONT_REF} {FONT_REF}))))')
    lines.append(f'    (property "Value" "{mod.name}" (at {x:.2f} {y - _symbol_height(mod) / 2 - 2.54:.2f} 0) (effects (font (size {FONT_REF} {FONT_REF}))))')
    for i in range(1, n_pins + 1):
        lines.append(f'    (pin "{i}" (uuid "{_uuid()}"))')
    lines.append(f'  )')
    return "\n".join(lines)


def _collect_nets(top_mod, sub_modules):
    """Build net label pairs from the top module's submodule instances."""
    nets = {}  # net_name -> list of (module_name, port_name, direction)
    mod_map = {m.name: m for m in sub_modules}

    for inst in top_mod.instances:
        sub = mod_map.get(inst.module_name)
        if not sub:
            continue
        port_map = {p.name: p for p in sub.ports}
        for port_name, net_expr in inst.connections.items():
            # Clean net expression
            net = re.sub(r'\[.*?\]', '', net_expr).strip()
            if not net:
                continue
            direction = "input"
            if port_name in port_map:
                direction = port_map[port_name].direction
            if net not in nets:
                nets[net] = []
            nets[net].append((inst.inst_name, inst.module_name, port_name, direction))
    return nets


def _emit_net_labels(top_mod, sub_modules, positions, lib_prefix):
    """Emit net_label entries connecting submodule ports."""
    lines = []
    mod_map = {m.name: m for m in sub_modules}

    for inst in top_mod.instances:
        sub = mod_map.get(inst.module_name)
        if not sub:
            continue
        pos = positions.get(inst.module_name)
        if not pos:
            continue
        x, y = pos
        half_h = _symbol_height(sub) / 2
        half_w = BOX_PAD_X

        port_map = {p.name: p for p in sub.ports}
        in_idx = 0
        out_idx = 0

        for port_name, net_expr in inst.connections.items():
            p = port_map.get(port_name)
            if not p:
                continue
            net = net_expr.strip()
            if not net:
                continue

            if p.direction == "input":
                pin_y = y + half_h - PIN_PITCH - in_idx * PIN_PITCH
                pin_x = x - half_w - PIN_LEN
                in_idx += 1
            else:
                pin_y = y + half_h - PIN_PITCH - out_idx * PIN_PITCH
                pin_x = x + half_w + PIN_LEN
                out_idx += 1

            lines.append(f'  (net_label "{net}" (at {pin_x:.2f} {pin_y:.2f} 0) (effects (font (size {FONT_REF} {FONT_REF}))) (uuid "{_uuid()}"))')

    return "\n".join(lines)


def generate_flat_schematic(top_mod, sub_modules, lib_prefix="half_cpu"):
    """Generate a flat .kicad_sch with all submodules on one sheet."""
    # Deduplicate: only one symbol per module type
    seen = set()
    unique_subs = []
    for inst in top_mod.instances:
        if inst.module_name not in seen:
            seen.add(inst.module_name)
            for m in sub_modules:
                if m.name == inst.module_name:
                    unique_subs.append(m)
                    break

    positions = _place_modules(unique_subs)

    lines = [
        '(kicad_sch',
        '  (version 20231120)',
        '  (generator "verilog_export")',
        '  (generator_version "1.0")',
        f'  (uuid "{_uuid()}")',
        '',
        '  (paper "A1")',
        '',
        '  (title_block',
        f'    (title "{top_mod.name} — Flat Architecture")',
        '    (comment 1 "Auto-generated by verilog_export")',
        '  )',
        '',
        _emit_lib_symbols(unique_subs, lib_prefix),
        '',
    ]

    # Place instances
    for i, mod in enumerate(unique_subs, 1):
        pos = positions[mod.name]
        lines.append(_emit_symbol_instance(mod, pos, i, lib_prefix))
        lines.append('')

    # Net labels
    lines.append('')
    lines.append(_emit_net_labels(top_mod, unique_subs, positions, lib_prefix))
    lines.append('')

    # Title text
    total_w = len(unique_subs) * GRID_X
    cx = ORIGIN_X + total_w / 2
    lines.append(f'  (text "{top_mod.name}" (at {cx:.2f} 25.4 0) (effects (font (size 5.08 5.08) bold)))')
    lines.append('')

    lines.append(')')
    return "\n".join(lines)


def generate_hier_schematic(top_mod, sub_modules, registry, lib_prefix="half_cpu"):
    """Generate a hierarchical schematic: root + per-category sub-sheets."""

    # Group submodules by category from their path
    categories = {}  # category_label -> [Module]
    mod_map = {m.name: m for m in sub_modules}
    inst_mod_names = [inst.module_name for inst in top_mod.instances]

    for mname in inst_mod_names:
        if mname not in mod_map or mname not in registry:
            continue
        mod_path = registry[mname]["path"]
        # Extract category from path: modules/<category>/<sub>/name
        rel = mod_path.split("/modules/")[-1] if "/modules/" in mod_path else mod_path
        parts = rel.split("/")
        if len(parts) >= 2:
            cat = parts[0]
            if parts[0] == "lib" and len(parts) >= 3:
                cat = f"lib/{parts[1]}"
            elif parts[0] in ("subsystem", "integration"):
                cat = parts[0]
        else:
            cat = "other"
        categories.setdefault(cat, [])
        m = mod_map[mname]
        if m not in categories[cat]:
            categories[cat].append(m)

    sheets = {}  # filename -> content
    sheet_info = []  # (sheet_name, filename, hierarchical_labels)

    # Generate one sub-sheet per category
    for cat, mods in sorted(categories.items()):
        sheet_name = cat.replace("/", "_").upper()
        fname = f"{cat.replace('/', '_')}.kicad_sch"
        positions = _place_modules(mods)

        # Collect hierarchical labels: nets that cross sheet boundaries
        h_labels_in = set()
        h_labels_out = set()
        for inst in top_mod.instances:
            if inst.module_name not in [m.name for m in mods]:
                continue
            sub = mod_map.get(inst.module_name)
            if not sub:
                continue
            port_map = {p.name: p for p in sub.ports}
            for pname, net in inst.connections.items():
                p = port_map.get(pname)
                if not p:
                    continue
                net_clean = net.strip()
                if p.direction == "input":
                    h_labels_in.add(net_clean)
                else:
                    h_labels_out.add(net_clean)

        slines = [
            '(kicad_sch',
            '  (version 20231120)',
            '  (generator "verilog_export")',
            '  (generator_version "1.0")',
            f'  (uuid "{_uuid()}")',
            '  (paper "A3")',
            '  (title_block',
            f'    (title "{top_mod.name} — {sheet_name}")',
            '    (comment 1 "Auto-generated sub-sheet")',
            '  )',
            '',
            _emit_lib_symbols(mods, lib_prefix),
            '',
        ]

        # Hierarchical labels
        hy = 40.64
        for net in sorted(h_labels_in):
            slines.append(f'  (hierarchical_label "{net}" (shape input) (at 25.4 {hy:.2f} 180) (effects (font (size {FONT_REF} {FONT_REF}))) (uuid "{_uuid()}"))')
            hy += 2.54
        for net in sorted(h_labels_out):
            slines.append(f'  (hierarchical_label "{net}" (shape output) (at 355.6 {hy:.2f} 0) (effects (font (size {FONT_REF} {FONT_REF}))) (uuid "{_uuid()}"))')
            hy += 2.54
        slines.append('')

        # Place instances
        for i, mod in enumerate(mods, 1):
            pos = positions[mod.name]
            slines.append(_emit_symbol_instance(mod, pos, i, lib_prefix))
            slines.append('')

        # Net labels
        slines.append(_emit_net_labels(top_mod, mods, positions, lib_prefix))
        slines.append('')

        slines.append(f'  (text "{sheet_name}" (at 190.5 25.4 0) (effects (font (size 3.81 3.81) bold)))')
        slines.append(')')

        sheets[fname] = "\n".join(slines)
        sheet_info.append((sheet_name, fname, sorted(h_labels_in), sorted(h_labels_out)))

    # Generate root sheet
    rlines = [
        '(kicad_sch',
        '  (version 20231120)',
        '  (generator "verilog_export")',
        '  (generator_version "1.0")',
        f'  (uuid "{_uuid()}")',
        '  (paper "A2")',
        '  (title_block',
        f'    (title "{top_mod.name} — Hierarchical Top")',
        '    (comment 1 "Auto-generated by verilog_export")',
        '  )',
        '  (lib_symbols)',
        '',
    ]

    # Place sheet blocks
    sx = 50.8
    for sname, sfname, h_in, h_out in sheet_info:
        n_pins = len(h_in) + len(h_out)
        sh_height = max(25.4, (n_pins + 2) * PIN_PITCH)
        sh_width = 76.2

        rlines.append(f'  (sheet')
        rlines.append(f'    (at {sx:.2f} 50.8) (size {sh_width:.2f} {sh_height:.2f})')
        rlines.append(f'    (stroke (width 0.254) (type solid))')
        rlines.append(f'    (fill (type background))')
        rlines.append(f'    (uuid "{_uuid()}")')
        rlines.append(f'    (property "Sheetname" "{sname}" (at {sx:.2f} 48.26 0) (effects (font (size 2.54 2.54) bold)))')
        rlines.append(f'    (property "Sheetfile" "{sfname}" (at {sx:.2f} {50.8 + sh_height + 1.27:.2f} 0) (effects (font (size {FONT_REF} {FONT_REF})) hide))')

        py = 55.88
        for net in h_in:
            rlines.append(f'    (pin "{net}" input (at {sx:.2f} {py:.2f} 180) (effects (font (size {FONT_SYM} {FONT_SYM}))) (uuid "{_uuid()}"))')
            py += PIN_PITCH
        for net in h_out:
            rlines.append(f'    (pin "{net}" output (at {sx + sh_width:.2f} {py:.2f} 0) (effects (font (size {FONT_SYM} {FONT_SYM}))) (uuid "{_uuid()}"))')
            py += PIN_PITCH

        rlines.append(f'  )')
        rlines.append('')
        sx += sh_width + 25.4

    # Title
    cx = sx / 2
    rlines.append(f'  (text "{top_mod.name} — Hierarchical Architecture" (at {cx:.2f} 25.4 0) (effects (font (size 5.08 5.08) bold)))')
    rlines.append('')

    # External port labels
    rlines.append('')
    ey = 160.02
    for p in top_mod.ports:
        shape = "input" if p.direction == "input" else "output"
        rlines.append(f'  (global_label "{p.label()}" (shape {shape}) (at 25.4 {ey:.2f} 0)')
        rlines.append(f'    (effects (font (size {FONT_REF} {FONT_REF}))) (uuid "{_uuid()}")')
        rlines.append(f'    (property "Intersheetref" "" (at 0 0 0) (effects (font (size {FONT_REF} {FONT_REF})) hide)))')
        ey += 5.08

    rlines.append('')
    rlines.append(')')

    root_name = f"{top_mod.name}_hier.kicad_sch"
    sheets[root_name] = "\n".join(rlines)

    return sheets


# ---------------------------------------------------------------------------
#  DigitalJS / CircuitVerse JSON generation
# ---------------------------------------------------------------------------

def _digitaljs_device_id():
    """Generate a unique device ID for DigitalJS."""
    _digitaljs_device_id._counter += 1
    return f"dev{_digitaljs_device_id._counter}"
_digitaljs_device_id._counter = -1


def generate_digitaljs(top_mod, sub_modules):
    """Generate a DigitalJS-compatible JSON dict from parsed Verilog modules.

    The output can be loaded in CircuitVerse or DigitalJS Online.
    Top-level ports become Input/Output devices; submodule types become
    subcircuit definitions; instances become Subcircuit device references
    wired together via connectors.
    """
    _digitaljs_device_id._counter = -1

    mod_map = {m.name: m for m in sub_modules}
    devices = {}
    connectors = []
    subcircuits = {}

    # --- Build subcircuit definitions for each unique submodule type ---
    for mod in sub_modules:
        if mod.name in subcircuits:
            continue
        sc_devices = {}
        for p in mod.inputs:
            did = f"{mod.name}_in_{p.name}"
            sc_devices[did] = {
                "type": "Input",
                "net": p.name,
                "order": 0,
                "bits": p.width,
            }
        for p in mod.outputs:
            did = f"{mod.name}_out_{p.name}"
            sc_devices[did] = {
                "type": "Output",
                "net": p.name,
                "order": 0,
                "bits": p.width,
            }
        # Assign display order
        for idx, did in enumerate(sc_devices):
            sc_devices[did]["order"] = idx
        subcircuits[mod.name] = {
            "devices": sc_devices,
            "connectors": [],
        }

    # --- Top-level Input devices for top module inputs ---
    top_input_devs = {}   # port_name -> device_id
    for p in top_mod.inputs:
        did = _digitaljs_device_id()
        devices[did] = {
            "type": "Input",
            "net": p.name,
            "order": 0,
            "bits": p.width,
            "label": p.name,
        }
        top_input_devs[p.name] = did

    # --- Top-level Output devices for top module outputs ---
    top_output_devs = {}  # port_name -> device_id
    for p in top_mod.outputs:
        did = _digitaljs_device_id()
        devices[did] = {
            "type": "Output",
            "net": p.name,
            "order": 0,
            "bits": p.width,
            "label": p.name,
        }
        top_output_devs[p.name] = did

    # Assign display order to top-level I/O
    for idx, did in enumerate(devices):
        devices[did]["order"] = idx

    # --- Subcircuit instances ---
    inst_devs = {}  # inst_name -> device_id
    for inst in top_mod.instances:
        sub = mod_map.get(inst.module_name)
        if not sub:
            continue
        did = _digitaljs_device_id()
        devices[did] = {
            "type": "Subcircuit",
            "celltype": inst.module_name,
            "label": inst.inst_name,
        }
        inst_devs[inst.inst_name] = did

    # --- Net map: collect which device+port drives/sinks each net ---
    # net_name -> {"drivers": [(dev_id, port)], "sinks": [(dev_id, port)]}
    net_map = {}

    def _add_net(net_name, dev_id, port_name, is_driver):
        net = re.sub(r'\[.*?\]', '', net_name).strip()
        if not net:
            return
        if net not in net_map:
            net_map[net] = {"drivers": [], "sinks": []}
        if is_driver:
            net_map[net]["drivers"].append((dev_id, port_name))
        else:
            net_map[net]["sinks"].append((dev_id, port_name))

    # Top-level inputs are drivers (they feed into the circuit)
    for p_name, did in top_input_devs.items():
        _add_net(p_name, did, "out", True)

    # Top-level outputs are sinks (they receive from the circuit)
    for p_name, did in top_output_devs.items():
        _add_net(p_name, did, "in", False)

    # Instance ports
    for inst in top_mod.instances:
        sub = mod_map.get(inst.module_name)
        if not sub:
            continue
        did = inst_devs.get(inst.inst_name)
        if not did:
            continue
        port_map = {p.name: p for p in sub.ports}
        for port_name, net_expr in inst.connections.items():
            p = port_map.get(port_name)
            if not p:
                continue
            # For the instance: input ports are sinks, output ports are drivers
            is_driver = p.direction == "output"
            _add_net(net_expr, did, port_name, is_driver)

    # --- Build connectors from net map ---
    for net_name, endpoints in net_map.items():
        for drv_id, drv_port in endpoints["drivers"]:
            for snk_id, snk_port in endpoints["sinks"]:
                conn = {
                    "from": {"id": drv_id, "port": drv_port},
                    "to": {"id": snk_id, "port": snk_port},
                    "name": net_name,
                }
                connectors.append(conn)

    result = {"devices": devices, "connectors": connectors}
    if subcircuits:
        result["subcircuits"] = subcircuits
    return result


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------

_FORMATS = ["kicad-flat", "kicad-hier", "kicad-sym", "digitaljs"]


def main():
    parser = argparse.ArgumentParser(
        description="Export Verilog modules to schematic formats."
    )
    parser.add_argument("module", help="Module name (resolved via manager.json)")
    parser.add_argument(
        "-f", "--format", default="kicad-flat", choices=_FORMATS,
        help="Output format (default: kicad-flat)",
    )
    parser.add_argument("-o", "--output", default="", help="Output directory (default: module's export/ subdir)")
    args = parser.parse_args()

    project_root = find_project_root("modules", "tools")
    modules_dir = os.path.join(project_root, "modules")
    registry = discover_modules(modules_dir)

    if args.module not in registry:
        # Fuzzy match
        matches = [n for n in registry if args.module.lower() in n.lower()]
        if len(matches) == 1:
            args.module = matches[0]
        elif matches:
            print(f"Ambiguous: {', '.join(matches)}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Unknown module: {args.module}", file=sys.stderr)
            sys.exit(1)

    info = registry[args.module]
    out_dir = args.output or os.path.join(info["path"], "export")
    os.makedirs(out_dir, exist_ok=True)

    lib_prefix = args.module

    # Parse the top module
    top_modules = parse_verilog(info["verilog"])
    top_mod = None
    for m in top_modules:
        if m.name == args.module.replace("-", "_"):
            top_mod = m
            break
    if not top_mod and top_modules:
        top_mod = top_modules[0]
    if not top_mod:
        print(f"Could not parse module from {info['verilog']}", file=sys.stderr)
        sys.exit(1)

    # Parse all dependency modules
    dep_paths = resolve_deps(args.module, registry)
    sub_modules = []
    seen_names = set()
    for vpath in dep_paths:
        if vpath == info["verilog"]:
            continue
        for m in parse_verilog(vpath):
            if m.name not in seen_names:
                seen_names.add(m.name)
                sub_modules.append(m)

    # Also parse the top module file for any helper modules
    for m in top_modules:
        if m.name != top_mod.name and m.name not in seen_names:
            seen_names.add(m.name)
            sub_modules.append(m)

    print(f"Parsed {top_mod.name}: {len(top_mod.ports)} ports, {len(top_mod.instances)} instances")
    print(f"Dependencies: {len(sub_modules)} sub-modules")

    fmt = args.format

    # --- DigitalJS ---
    if fmt == "digitaljs":
        djs = generate_digitaljs(top_mod, sub_modules)
        djs_path = os.path.join(out_dir, f"{args.module}.digitaljs.json")
        with open(djs_path, "w") as f:
            json.dump(djs, f, indent=2)
        print(f"  -> {os.path.relpath(djs_path, project_root)}")
        return

    # --- KiCad formats ---
    all_mods = sub_modules + [top_mod]
    sym_content = generate_sym_lib(all_mods, lib_prefix)
    sym_path = os.path.join(out_dir, f"{args.module}.kicad_sym")
    with open(sym_path, "w") as f:
        f.write(sym_content)
    print(f"  -> {os.path.relpath(sym_path, project_root)}")

    if fmt == "kicad-sym":
        return

    if fmt == "kicad-hier":
        sheets = generate_hier_schematic(top_mod, sub_modules, registry, lib_prefix)
        for fname, content in sheets.items():
            fpath = os.path.join(out_dir, fname)
            with open(fpath, "w") as f:
                f.write(content)
            print(f"  -> {os.path.relpath(fpath, project_root)}")
    else:
        flat_content = generate_flat_schematic(top_mod, sub_modules, lib_prefix)
        flat_path = os.path.join(out_dir, f"{args.module}_flat.kicad_sch")
        with open(flat_path, "w") as f:
            f.write(flat_content)
        print(f"  -> {os.path.relpath(flat_path, project_root)}")


if __name__ == "__main__":
    main()
