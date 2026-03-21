# Project Conventions

## Tools structure

Each tool lives in its own subdirectory under `tools/`:

```
tools/
  <tool-name>/
    <tool-name>.py    # main script
    README.md         # usage docs
    *.asm / *.hex     # example/data files (if any)
```

When adding a new tool, create a folder with a `README.md` and the main script named after the tool.

## Manager convention

Any folder can contain a `.manager/` subdirectory with a `manager.py` script that helps interact with the contents of that folder:

```
<folder>/
  .manager/
    manager.py    # helper script for this folder
    README.md     # usage docs
```

For example, `test/.manager/manager.py` displays module documentation with Rich rendering:

```bash
python test/.manager/manager.py           # interactive selection
python test/.manager/manager.py alu       # show specific module docs
```

## Source structure

- `src/` — Verilog source modules
- `test/` — cocotb testbenches, one subdirectory per module
  - `test/<module>/` — `tb_*.v`, `test_*.py`, `Makefile`
  - `test/.manager/` — helper script for browsing docs
  - `test/artifacts/` — shared build artifacts (gitignored)
- `docs/` — one `.md` per module

## Source

Don't use behavioral code

## Testing

Tests use cocotb + Icarus Verilog. Each module has its own directory with a Makefile:

```bash
source .venv/bin/activate
export PATH="/opt/homebrew/bin:$PATH"
cd test/<module> && make
```

## Tools

All tools are designed to run from the **project root**. They accept **module names** instead of full paths when meaningful (e.g. `spi` instead of `test/artifacts/tb_spi_slave.fst`). When a name is ambiguous, tools prompt for interactive selection.

## Naming

- Verilog ports: `i_` input, `o_` output
- Verilog wires: `w_` prefix
- Verilog regs: `r_` prefix
- Parameters: UPPER_CASE
