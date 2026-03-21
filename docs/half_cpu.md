[Back to Main](../README.md)

# Half CPU - CPU Core with External Memory over SPI

> **Multi-cycle CPU with PC, decoder, regfile, and ALU — all memory access via SPI**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `pc` | out | 8 | Current program counter (debug) |
| `alu` | out | 8 | ALU result (debug) |
| `state` | out | 4 | FSM state (debug) |
| `spi_tx_data` | out | 16 | SPI TX data (cmd+addr or data) |
| `spi_tx_load` | out | 1 | SPI TX load pulse |
| `spi_rx_data` | in | 16 | SPI RX data (instruction or memory data) |
| `spi_rx_done` | in | 1 | SPI RX complete pulse |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## Architecture

Unlike `cpu.v` which is single-cycle with internal ROM, `half_cpu` is multi-cycle and fetches everything over SPI:

```
                              i_clk ──┐  i_rst_n ──┐
                                      │             │
  ┌───────────────────────────────────┼─────────────┼──────────────────────────┐
  │ half_cpu                          ▼             ▼                          │
  │                                                                            │
  │            mem bus                                                         │
  │  ┌──────────┐ ◀──────────▶ ┌──────────┐                                   │
  │  │ mem_ctrl │              │ cpu_fsm  │                                    │
  │  └────┬─────┘              └──┬───────┘                                    │
  │       │                       │ instr_en, reg_we, pc_en, load_data_sel     │
  │  SPI TX/RX                    │                                            │
  │       │                       ▼                                            │
  │       │               ┌─────────────┐  i_spi_rx_data                      │
  │       │               │  instr_reg  │◀───────────────                      │
  │       │               │   16-bit    │                                      │
  │       │               └──────┬──────┘                                      │
  │       │                      │ instr[15:0]                                 │
  │       │                      ▼                                             │
  │       │               ┌─────────────┐                                      │
  │       │               │   Decoder   │                                      │
  │       │               └─────────────┘                                      │
  │       │            rs1,rs2│  │rd,we  │imm8  │imm6  │alu_src               │
  │       │              ┌────┘  │       │      │      │                       │
  │       │              ▼       ▼       │      │      │                       │
  │       │          ┌──────────────┐    │      │      │                       │
  │       │          │   Regfile    │    │      │      │                       │
  │       │          │    8 x 8    │    │      │      │                       │
  │       │          └──────────────┘    │      │      │                       │
  │       │          rd1 │      │ rd2    │      │      │                       │
  │       │              │      ▼        │      ▼      ▼                       │
  │       │              │  ┌────────────┴──────────────┐                      │
  │       │              │  │       ALU B Mux           │                      │
  │       │              │  │  rd2 / sign-ext(imm6)     │                      │
  │       │              │  └───────────┬───────────────┘                      │
  │       │              │              │ alu_b                                │
  │       │              ▼              ▼                                      │
  │       │          ┌──────────────────────┐                                   │
  │       │          │        ALU           │                                   │
  │       │          │       9 ops          │                                   │
  │       │          └──────────┬───────────┘                                   │
  │       │                     │ alu_result                                    │
  │       │                     ▼                                              │
  │       │  ┌──────────────────────────────────────┐                          │
  │       │  │         Writeback Mux (3-way)        │                          │
  │       │  │  0: ALU result                       │                          │
  │       │  │  1: imm8 (LDI)                       │                          │
  │       │  │  2: spi_rx_data[7:0] (LOAD)          │                          │
  │       │  └──────────────────┬───────────────────┘                          │
  │       │                     │ write_data                                   │
  │       │                     ▼                                              │
  │       │               ┌──────────┐                                         │
  │       │               │ Regfile  │                                         │
  │       │               │ (write)  │                                         │
  │       │               └──────────┘                                         │
  │       │                                                                    │
  │       │          ┌──────────┐                                              │
  │       │          │    PC    │──── jump/beq logic                           │
  │       │          │  8-bit   │◀── imm8 (load addr)                         │
  │       │          └──────────┘                                              │
  │       │                                                                    │
  ├───────┼─── o_spi_tx_data[15:0] ──▶                                        │
  ├───────┼─── o_spi_tx_load ────────▶                                        │
  │ ◀─────┼─── i_spi_rx_data[15:0]                                            │
  │ ◀─────┼─── i_spi_rx_done                                                  │
  │       │                                                                    │
  ├───────┴─── o_pc[7:0]                                                       │
  ├──────────── o_alu[7:0]                                                     │
  ├──────────── o_state[5:0]  {mem_state[2:0], cpu_state[2:0]}                │
  └────────────────────────────────────────────────────────────────────────────┘
```

## Key Differences from `cpu.v`

| | `cpu.v` | `half_cpu.v` |
|---|---|---|
| Memory | Internal ROM | External via SPI |
| Cycle | Single-cycle | Multi-cycle (FSM) |
| PC advance | Every clock | Only on FSM `WRITEBACK` |
| LOAD/STORE | Not wired | Full SPI protocol |
| Writeback sources | ALU, imm8 | ALU, imm8, SPI RX (LOAD) |

## Writeback Mux

3-way mux selects what gets written to the register file:

| Select | Source | When |
|--------|--------|------|
| 0 | ALU result | R-type, ADDI |
| 1 | imm8 | LDI |
| 2 | SPI RX data[7:0] | LOAD |

## Dependencies

`cpu_fsm.v`, `pc.v`, `decoder.v`, `regfile.v`, `alu.v`, `mux.v`, `register.v`, `dff.v`, `kogge-stone.v`

---
[Back to Main](../README.md)
