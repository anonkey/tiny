# Project Conventions

## Module structure (monorepo)

Each Verilog module is a self-contained package under `modules/`:

```
modules/<category>/<name>/
  <name>.v              # source
  <name>.md             # documentation (starts with > **summary** blockquote)
  manager.json          # {"name": "<name>", "deps": ["dep1", "dep2"]}
  test/                 # optional: tb_<name>.v + test_<name>.py
```

Dependencies in `manager.json` use module names (not paths). The manager resolves names to paths by scanning all `manager.json` files.

Categories mirror the hardware hierarchy:
- `lib/cells/` — primitives (dff, mux, zero_flag)
- `lib/core/` — datapath (alu, decoder, regfile, register, pc, rom, etc.)
- `lib/spi/` — SPI components (cdc_sync, shift registers, byte counter)
- `lib/mem/` — memory (read_data_accum)
- `subsystem/` — controllers (cpu_fsm, mem_ctrl, spi_slave)
- `integration/` — top-level (cpu, half_cpu, top)

Placement rules:
- Stateless or single-purpose block → `lib/<domain>/`
- Owns a state machine or protocol → `subsystem/`
- Wires multiple domains together → `integration/`

## Tools structure

Each tool lives in its own subdirectory under `tools/`:

```
tools/
  <tool-name>/
    <tool-name>.py    # main script
    README.md         # usage docs
```

The unified manager lives in `tools/manager/` with `manager.py` and `manager_utils.py`.

Root `manage.py` is a thin wrapper that dispatches to `tools/manager/manager.py`.

## Build and test

Tests use cocotb + Icarus Verilog. A shared Makefile (`tools/Makefile.sim`) is used for all modules — the manager injects `VERILOG_SOURCES` from transitive dependency resolution.

```bash
# Via manager (recommended)
python manage.py --run <module>          # run tests
python manage.py --run <module> --fst    # run with FST waveforms
python manage.py --deps <module>         # show dependency tree

# Interactive
python manage.py                         # packages / tools selector
```

## TinyTapeout compatibility

`src/` contains symlinks to `modules/` for TinyTapeout build system compatibility. `info.yaml` references files relative to `src/`.

## Source

Don't use behavioral code.

## Tools

All tools are designed to run from the **project root**. They accept **module names** instead of full paths when meaningful. When a name is ambiguous, tools prompt for interactive selection.

## Naming

- Verilog ports: `i_` input, `o_` output
- Verilog wires: `w_` prefix
- Verilog regs: `r_` prefix
- Parameters: UPPER_CASE
