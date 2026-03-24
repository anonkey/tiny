[Back to Main](../README.md)

# Half CPU - CPU Core with External Memory over SPI

> **Multi-cycle CPU with PC, decoder, regfile, ALU, and integrated SPI interface — all memory access via byte-by-byte SPI (nvSRAM-compatible)**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `pc` | out | 8 | Current program counter (debug) |
| `alu` | out | 8 | ALU result (debug) |
| `state` | out | 7 | FSM state: {mem_state[3:0], cpu_state[2:0]} |
| `timeout` | out | 1 | SPI timeout pulse from mem_ctrl |
| `mosi` | out | 1 | SPI master-out (TX to nvSRAM) |
| `miso` | in | 1 | SPI master-in (RX from nvSRAM) |
| `cs_n` | out | 1 | SPI chip select (active low) |
| `sclk` | in | 1 | SPI clock (external) |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## Architecture

Integrates `cpu_fsm`, `mem_ctrl`, and `spi_phy` internally. Only 4 physical SPI wires are exposed:

```
                              i_clk ──┐  i_rst_n ──┐
                                      │             │
  ┌───────────────────────────────────┼─────────────┼──────────────────────────┐
  │ half_cpu                          ▼             ▼                          │
  │                                                                            │
  │            mem bus                                                         │
  │  ┌──────────┐ ◀──────────▶ ┌──────────┐                                   │
  │  │ mem_ctrl │              │ cpu_fsm  │                                    │
  │  │          │              └──┬───────┘                                    │
  │  │ CS_n ────┤─────────────────┤ instr_en, reg_we, pc_en                   │
  │  │ tx_data ─┤     read_data   │                                            │
  │  │ tx_load ─┤──────┐         ▼                                            │
  │  │ rx_data ◀┤      │  ┌─────────────┐                                     │
  │  │ byte_done◀─┐    └─▶│  instr_reg  │                                     │
  │  └──────────┘ │       └──────┬──────┘                                      │
  │       │       │              │ instr[15:0]                                 │
  │       ▼       │              ▼                                             │
  │  ┌──────────┐ │       ┌─────────────┐                                      │
  │  │spi_phy │ │       │   Decoder   │                                      │
  │  │  8-bit   │ │       └─────────────┘                                      │
  │  │ shift    │ │          │       │                                         │
  │  │ regs     │ │          ▼       ▼                                         │
  │  └──┬───┬──┘ │   ┌──────────┐ ┌──────────┐                                │
  │     │   │     │   │ Regfile  │ │   ALU    │                                │
  │     │   │     │   └──────────┘ └────┬─────┘                                │
  │     │   │     │                     │                                      │
  │     │   │     │   ┌─────────────────┴──────────┐                           │
  │     │   │     │   │  Writeback Mux (3-way)     │                           │
  │     │   │     │   │  0: ALU  1: imm8  2: LOAD  │                           │
  │     │   │     │   └────────────────────────────┘                           │
  │     │   │     │                                                            │
  │     │   │     │   ┌──────────┐                                             │
  │     │   │     │   │    PC    │                                             │
  │     │   │     │   └──────────┘                                             │
  │     │   │     │                                                            │
  ├─────┴───┼─────┼─── o_mosi ──────────────▶  (SPI data out to nvSRAM)       │
  │ ◀───────┤     │─── i_miso               (SPI data in from nvSRAM)        │
  ├─────────┼─────┼─── o_cs_n ──────────────▶  (chip select, driven by        │
  │ ◀───────┤     │                             mem_ctrl)                      │
  │ ◀───────┴─────┼─── i_sclk               (SPI clock, external)            │
  │               │                                                            │
  ├───────────────┴─── o_pc[7:0]                                               │
  ├──────────────────── o_alu[7:0]                                             │
  ├──────────────────── o_state[6:0]  {mem_state[3:0], cpu_state[2:0]}        │
  └────────────────────────────────────────────────────────────────────────────┘
```

## Key Differences from `cpu.v`

| | `cpu.v` | `half_cpu.v` |
|---|---|---|
| Memory | Internal ROM | External via SPI |
| Cycle | Single-cycle | Multi-cycle (FSM) |
| PC advance | Every clock | Only on FSM `WRITEBACK` |
| LOAD/STORE | Not wired | Full nvSRAM SPI protocol |
| SPI | None | Integrated spi_phy, 4-wire bus |

## Writeback Mux

3-way mux selects what gets written to the register file:

| Select | Source | When |
|--------|--------|------|
| 0 | ALU result | R-type, ADDI |
| 1 | imm8 | LDI |
| 2 | read_data[7:0] | LOAD |

## Data Flow

The instruction register and writeback mux both read from `mem_ctrl.o_read_data` (not directly from SPI RX). `mem_ctrl` accumulates individual SPI RX bytes into a 16-bit word:
- **FETCH**: 2 RX bytes → `read_data = {hi_byte, lo_byte}` → 16-bit instruction
- **LOAD**: 1 RX byte → `read_data[7:0] = data_byte` → 8-bit register write

## Dependencies

`cpu_fsm.v`, `mem_ctrl.v`, `spi_phy.v`, `pc.v`, `decoder.v`, `regfile.v`, `alu.v`, `alu_operand_mux.v`, `zero_flag.v`, `writeback_mux.v`, `mux.v`, `register.v`, `dff.v`, `kogge-stone.v`, `cdc_sync.v`, `spi_shift_tx.v`, `spi_shift_rx.v`, `spi_byte_counter.v`, `read_data_accum.v`, `pipeline_reg.v`

---
[Back to Main](../README.md)
