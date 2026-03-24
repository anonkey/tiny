# Waveform

> **Generic FST/VCD trace analysis tool for debugging simulations**

All commands accept a **module name** (e.g. `spi`, `half_cpu`, `pc`) instead of a file path. The tool resolves it to `test/tb_<module>.fst` automatically. If ambiguous, it prompts for interactive selection.

## Usage

### List signals

```bash
python tools/waveform/waveform.py signals spi
python tools/waveform/waveform.py signals half_cpu --filter "pc|state|spi"
python tools/waveform/waveform.py signals spi_phy -f "sclk|mosi|cs" -n 20
```

### Dump transitions

Show when signal values change:

```bash
python tools/waveform/waveform.py transitions half_cpu "state" "pc_out" --max 15
python tools/waveform/waveform.py transitions spi "rx_done" --max 10 --format bin
```

Output:
```
→ half_cpu (test/tb_half_cpu.fst)

--- tb_half_cpu.state[3:0] ---
       0.0ns: 0x0
      30.0ns: 0x9
      40.0ns: 0x1
      ...
```

### Sample table

Sample multiple signals at regular intervals or on clock edges:

```bash
# Fixed 10ns step
python tools/waveform/waveform.py table half_cpu "pc_out" "state" "spi_tx_load" --step 10

# On rising clock edges
python tools/waveform/waveform.py table half_cpu "pc_out" "state" --clock clk --edge rising -n 30
```

Output:
```
      Time          pc_out[7:0]           state[3:0]          spi_tx_load
---------------------------------------------------------------------------
       0ns                 0x0                  0x0                  0x0
      30ns                 0x0                  0x9                  0x1
      ...
```

### Waveform display

Render signals as Unicode waveforms in the terminal:

```bash
python tools/waveform/waveform.py wave spi "sclk" "mosi" "cs_n" "rx_done"
python tools/waveform/waveform.py wave half_cpu "clk" "state" "pc_out" --width 100
python tools/waveform/waveform.py wave half_cpu "clk" "state" --start 10 --end 50
```

Output:
```
clk         │____╱▔▔▔▔╲____╱▔▔▔▔╲___╱▔▔▔▔╲____╱▔▔▔▔╲____╱▔▔▔╲
rst_n       │_________╱▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
state[3:0]  │═════0x0══════│══0x1═══│═══0x2═══│═══0x3═══│══0x4═══
pc[7:0]     │═════0x0══════│══0x1═══│═══0x2═══│═══0x3═══│══0xA═══
            │|0ns       |12ns      |23ns      |35ns      |47ns
```

1-bit signals render as classic digital waveforms (`▔` high, `_` low, `╱` rising, `╲` falling).
Multi-bit signals show hex/bin/dec values centered between `═` rails.

## Signal matching

Signal names can be specified as:
- **Exact**: `tb_half_cpu.state[3:0]`
- **Glob**: `tb_half_cpu.dut.*pc*`
- **Substring**: `spi_tx_load` (matches any signal containing this string)

When a substring matches more than 10 signals, the tool prompts you to pick one interactively.

## Options

| Flag | Subcommand | Description |
|------|------------|-------------|
| `--filter REGEX` | signals | Filter signal names by regex |
| `--max N` | all | Limit output rows / transitions |
| `--format {hex,bin,dec}` | transitions, table, wave | Value display format (default: hex) |
| `--width W` | wave | Terminal width (default: auto-detect) |
| `--start T` | wave | Start time (in file's time unit) |
| `--end T` | wave | End time (in file's time unit) |
| `--step N` | table | Sample interval in ns (default: 10) |
| `--clock SIG` | table | Sample on clock edges instead of fixed step |
| `--edge {rising,falling,both}` | table | Which clock edge to sample (default: rising) |

## Requirements

- `vcdvcd` (already in project venv)
