# Manager

> **Unified manager for module dependency resolution, test execution, and tool dispatch**

## Usage

```bash
python manage.py                              # interactive (packages / tools)
python manage.py alu                          # show ALU actions
python manage.py --run alu                    # run ALU tests
python manage.py --run alu --fst              # run with FST waveforms
python manage.py --run-all                    # run all testable modules
python manage.py --deps half_cpu              # show dependency tree
python manage.py --tool assembler -- --help   # run tool directly
python manage.py --export-all                 # export all modules (circuitverse-yosys --gate)
```

## Commands

| Flag | Description |
|------|-------------|
| `--run <module>` | Run tests for a single module (resolves transitive deps) |
| `--run <module> --fst` | Run tests with FST waveform output |
| `--run-all` | Run tests for all testable modules |
| `--deps <module>` | Show dependency tree |
| `--tool <name> -- <args>` | Run a tool with arguments |
| `--export-all` | Export all modules via verilog_export |
| *(no flags)* | Interactive menu (packages / tools) |
| `<module>` | Interactive actions for a specific module |

## Architecture

| File | Role |
|------|------|
| `manager.py` | CLI entry point and dispatch |
| `manager_utils.py` | Module discovery, dependency resolution, console helpers |
| `manager_modules.py` | Test runner, dependency tree, interactive module menu |
| `manager_tools.py` | Tool listing, example extraction, interactive tool REPL |

## Module Discovery

Scans all `manager.json` files under `modules/` to build a registry of module names, paths, and dependencies. Names are resolved with fuzzy matching — partial names work (e.g. `alu` matches `alu`).

## Test Runner

Uses the shared `tools/Makefile.sim` for simulation. Automatically resolves transitive dependencies and injects `VERILOG_SOURCES` into the Makefile.

## Requirements

- `rich` (console output)
- `simple-term-menu` (optional, for arrow-key selection)
