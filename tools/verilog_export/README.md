> **Export Verilog modules to CircuitVerse JSON**

## Usage

```bash
# CircuitVerse (block-level subcircuits)
python tools/verilog_export/verilog_export.py half_cpu -f circuitverse

# CircuitVerse (gate-level via Yosys synthesis)
python tools/verilog_export/verilog_export.py half_cpu -f circuitverse-yosys

# CircuitVerse (hierarchical via Yosys, preserves module boundaries)
python tools/verilog_export/verilog_export.py half_cpu -f circuitverse-yosys-hier

# Hierarchical with scope caching (routes leaves once, reuses on repeat)
python tools/verilog_export/verilog_export.py half_cpu -f circuitverse-yosys-hier --cache

# Gate-level hierarchical (each module decomposed to primitives, cached)
python tools/verilog_export/verilog_export.py half_cpu -f circuitverse-yosys-hier --gate --cache

# Custom output directory
python tools/verilog_export/verilog_export.py half_cpu -o build/export
```

By default, output goes to `<module_dir>/export/`.

## Formats

| `-f` / `--format` | Output |
|------------|--------|
| `circuitverse` | `.cv.json` — block-level with SubCircuit scopes |
| `circuitverse-yosys` | `.gate.cv.json` — gate-level (AND/OR/NOT/DFF/MUX) via Yosys |
| `circuitverse-yosys-hier` | `.hlsynth-hier.cv.json` — hierarchical with SubCircuit scopes via Yosys |

## CircuitVerse formats

**`circuitverse`** — uses the project's own parser. Each submodule becomes a CircuitVerse SubCircuit scope with Input/Output ports. No external tools needed.

**`circuitverse-yosys`** — synthesizes the full design through Yosys (`flatten → techmap → abc`) down to individual gates. Requires `yosys` on PATH. Produces real AND, OR, NOT, NAND, NOR, XOR, XNOR, MUX and DFF components.

**`circuitverse-yosys-hier`** — elaborates through Yosys without flattening, preserving module hierarchy. Each module becomes a SubCircuit scope with independently routed internals. SubCircuit instances use the same pin-count-based column spacing (`pin_clearance` / `compute_col_x`) and vertical padding (`V_CELL_PAD`) as base components, and clearance verification covers both equally. Supports `--gate` to decompose each module to 1-bit primitives (AND/OR/NOT/DFF/MUX). With `--cache`, routed scopes are saved to disk (keyed by source MD5) so that unchanged modules are placed and routed only once across repeated exports. Stale caches are auto-pruned.

## Code structure

```
verilog_export/
├── verilog_export.py        # CLI entry point
├── verilog_parser.py        # Verilog source parser
├── common/                  # Shared constants, emitters, node allocator, utilities
├── synthesis/
│   ├── hierarchical/        # Block-level and Yosys-based scope generation
│   └── gates/               # Component handlers (AND, OR, DFF, ALU, …) + registry
├── placement/               # Topological sort, column layout, port placement
├── routing/                 # A* orthogonal wire router
└── verification/            # Post-routing checks, ASCII diagram renderer
```

## Limitations

- Generate blocks (`genvar` loops) are not expanded in block-level formats
