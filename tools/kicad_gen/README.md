> **Generate KiCad schematics (.kicad_sch) and symbol libraries (.kicad_sym) from Verilog modules**

## Usage

```bash
# Flat schematic (all submodules on one sheet)
python tools/kicad_gen/kicad_gen.py alu

# Hierarchical schematic (sub-sheets grouped by category)
python tools/kicad_gen/kicad_gen.py half_cpu --hier

# Symbol library only
python tools/kicad_gen/kicad_gen.py cpu_fsm --sym-only

# Custom output directory
python tools/kicad_gen/kicad_gen.py half_cpu -o build/kicad

# DigitalJS / CircuitVerse JSON
python tools/kicad_gen/kicad_gen.py half_cpu --digitaljs
```

By default, output goes to `<module_dir>/kicad/`.

## What it does

1. Parses the Verilog source (module header, ports, parameters, submodule instantiations)
2. Resolves dependencies via `manager.json` (reuses the project's manager system)
3. Generates:
   - `.kicad_sym` — symbol library with all modules (ALU gets trapezoid, muxes get wedge, others get rectangles)
   - `.kicad_sch` — schematic with placed symbols and net labels connecting ports

## Modes

| Flag | Output |
|------|--------|
| *(default)* | Flat schematic + symbol lib |
| `--hier` | Root sheet + per-category sub-sheets + symbol lib |
| `--sym-only` | Symbol library only |
| `--digitaljs` | DigitalJS JSON (load in CircuitVerse or digitaljs.tilk.eu) |

## Hierarchical grouping

With `--hier`, modules are grouped into sub-sheets by their category path:
- `lib/cells/` — primitives (dff, mux)
- `lib/core/` — datapath (alu, decoder, regfile, pc, ...)
- `subsystem/` — controllers (cpu_fsm, mem_ctrl, spi_slave)

## Limitations

- Layout is left-to-right linear — adjust placement in KiCad GUI
- Symbols are embedded inline (no external library path needed)
- Generate blocks (`genvar` loops) are not expanded — only named instantiations are captured
