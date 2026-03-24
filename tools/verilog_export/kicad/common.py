"""Shared KiCad schematic helpers: placement, symbol emission, net labels."""

from kicad.utils import _uuid
from kicad.symbol import (
    PIN_LEN, PIN_PITCH, BOX_PAD_X, FONT_SYM, FONT_REF,
    _symbol_height, generate_symbol,
)

# Placement grid
GRID_X = 76.2   # horizontal spacing between modules
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
