"""KiCad symbol generation for Verilog modules."""

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
