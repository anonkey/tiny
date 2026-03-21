> **Export Verilog modules to KiCad schematics or DigitalJS JSON (CircuitVerse compatible)**

## Usage

```bash
# KiCad flat schematic (default)
python tools/verilog_export/verilog_export.py alu

# KiCad hierarchical schematic (sub-sheets grouped by category)
python tools/verilog_export/verilog_export.py half_cpu --format kicad-hier

# KiCad symbol library only
python tools/verilog_export/verilog_export.py cpu_fsm --format kicad-sym

# DigitalJS / CircuitVerse JSON
python tools/verilog_export/verilog_export.py half_cpu --format digitaljs

# Custom output directory
python tools/verilog_export/verilog_export.py half_cpu -o build/export
```

By default, output goes to `<module_dir>/export/`.

## What it does

1. Parses the Verilog source (module header, ports, parameters, submodule instantiations)
2. Resolves dependencies via `manager.json` (reuses the project's manager system)
3. Exports to the selected format

## Formats

| `--format` | Output |
|------------|--------|
| `kicad-flat` *(default)* | Flat `.kicad_sch` + `.kicad_sym` |
| `kicad-hier` | Root sheet + per-category sub-sheets + `.kicad_sym` |
| `kicad-sym` | `.kicad_sym` symbol library only |
| `digitaljs` | `.digitaljs.json` — load in [CircuitVerse](https://circuitverse.org) or [DigitalJS Online](https://digitaljs.tilk.eu) |

## KiCad hierarchical grouping

With `kicad-hier`, modules are grouped into sub-sheets by their category path:
- `lib/cells/` — primitives (dff, mux)
- `lib/core/` — datapath (alu, decoder, regfile, pc, ...)
- `subsystem/` — controllers (cpu_fsm, mem_ctrl, spi_slave)

## Limitations

- KiCad layout is left-to-right linear — adjust placement in KiCad GUI
- KiCad symbols are embedded inline (no external library path needed)
- Generate blocks (`genvar` loops) are not expanded — only named instantiations are captured
- DigitalJS subcircuits define port interfaces only (no internal gate-level logic)
