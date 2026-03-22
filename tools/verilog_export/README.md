> **Export Verilog modules to KiCad schematics or CircuitVerse JSON**

## Usage

```bash
# KiCad flat schematic (default)
python tools/verilog_export/verilog_export.py alu

# KiCad hierarchical schematic (sub-sheets grouped by category)
python tools/verilog_export/verilog_export.py half_cpu -f kicad-hier

# KiCad symbol library only
python tools/verilog_export/verilog_export.py cpu_fsm -f kicad-sym

# CircuitVerse (block-level subcircuits)
python tools/verilog_export/verilog_export.py half_cpu -f circuitverse

# CircuitVerse (gate-level via Yosys synthesis)
python tools/verilog_export/verilog_export.py half_cpu -f circuitverse-yosys

# Custom output directory
python tools/verilog_export/verilog_export.py half_cpu -o build/export
```

By default, output goes to `<module_dir>/export/`.

## Formats

| `-f` / `--format` | Output |
|------------|--------|
| `kicad-flat` *(default)* | Flat `.kicad_sch` + `.kicad_sym` |
| `kicad-hier` | Root sheet + per-category sub-sheets + `.kicad_sym` |
| `kicad-sym` | `.kicad_sym` symbol library only |
| `circuitverse` | `.cv.json` — block-level with SubCircuit scopes |
| `circuitverse-yosys` | `.gate.cv.json` — gate-level (AND/OR/NOT/DFF/MUX) via Yosys |

## CircuitVerse formats

**`circuitverse`** — uses the project's own parser. Each submodule becomes a CircuitVerse SubCircuit scope with Input/Output ports. No external tools needed.

**`circuitverse-yosys`** — synthesizes the full design through Yosys (`flatten → techmap → abc`) down to individual gates. Requires `yosys` on PATH. Produces real AND, OR, NOT, NAND, NOR, XOR, XNOR, MUX and DFF components.

## KiCad hierarchical grouping

With `kicad-hier`, modules are grouped into sub-sheets by their category path:
- `lib/cells/` — primitives (dff, mux)
- `lib/core/` — datapath (alu, decoder, regfile, pc, ...)
- `subsystem/` — controllers (cpu_fsm, mem_ctrl, spi_slave)

## Limitations

- KiCad layout is left-to-right linear — adjust placement in KiCad GUI
- KiCad symbols are embedded inline (no external library path needed)
- Generate blocks (`genvar` loops) are not expanded in block-level formats
