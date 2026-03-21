[Back to Main](../README.md)

# Memory Controller - SPI Protocol Handler

> **Translates abstract memory requests into SPI two-phase half-duplex transactions (nvSRAM-compatible)**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `spi_tx_data` | out | 16 | Data to load into SPI TX shift register |
| `spi_tx_load` | out | 1 | Pulse to trigger SPI TX |
| `spi_rx_done` | in | 1 | SPI RX complete pulse |
| `mem_req` | in | 1 | Pulse: start memory operation |
| `mem_op` | in | 2 | Operation: 00=FETCH, 01=LOAD, 10=STORE |
| `mem_addr` | in | 8 | Address |
| `mem_wdata` | in | 8 | Write data (STORE only) |
| `mem_done` | out | 1 | Pulse: operation complete |
| `state` | out | 3 | Current FSM state (debug) |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## Architecture

```
                              i_clk ──┐  i_rst_n ──┐
                                      │             │
  ┌───────────────────────────────────┼─────────────┼─────────────────────────┐
  │ mem_ctrl                          ▼             ▼                         │
  │                                                                           │
  │  From cpu_fsm:                                                            │
  │  ──▶ i_mem_req ──┐                                                        │
  │  ──▶ i_mem_op ───┤  ┌──────────────┐                                      │
  │  ──▶ i_mem_addr ─┼─▶│ Latch Regs   │  (captured on IDLE & mem_req)        │
  │  ──▶ i_mem_wdata ┘  │ r_op, r_addr │                                      │
  │                     │ r_wdata      │                                      │
  │                     └──────┬───────┘                                      │
  │                            │                                              │
  │                    r_op    │   r_addr                                     │
  │                      │     │     │                                        │
  │                      ▼     │     │                                        │
  │               ┌────────────┴┐    │                                        │
  │               │ Opcode Mux  │    │                                        │
  │               │ (4-way)     │    │                                        │
  │               │ 0: IFETCH   │    │                                        │
  │               │    0x03     │    │                                        │
  │               │ 1: LOAD     │    │                                        │
  │               │    0x0B     │    │                                        │
  │               │ 2: STORE    │    │                                        │
  │               │    0x02     │    │                                        │
  │               └──────┬──────┘    │                                        │
  │                      │ opcode    │                                        │
  │                      ▼           ▼                                        │
  │  ┌──────────┐   ┌──────────────────────┐                                  │
  │  │  State   │──▶│   SPI TX Data Reg    │                                  │
  │  │   FSM    │   │                      │                                  │
  │  │          │   │ WREN: {0x06, 0x00}   │                                  │
  │  │ IDLE     │   │ CMD:  {opc,  addr}   │──── o_spi_tx_data[15:0] ──▶     │
  │  │ TX_WREN  │   │ DATA: {0x00, wdata}  │                                  │
  │  │ WAIT_WREN│   └──────────────────────┘                                  │
  │  │ TX_CMD   │                                                             │
  │  │ WAIT_CMD │   ┌──────────────────────┐                                  │
  │  │ TX_DATA  │──▶│   SPI TX Load FF     │──── o_spi_tx_load ─────────▶    │
  │  │ WAIT_DATA│   └──────────────────────┘                                  │
  │  │ RX_WAIT  │                                                             │
  │  └──────────┘   ┌──────────────────────┐                                  │
  │       │    ◀────│   i_spi_rx_done      │◀─────────────────────────────    │
  │       │         └──────────────────────┘                                  │
  │       ▼                                                                   │
  │  ┌──────────────────────┐                                                 │
  │  │   Mem Done FF        │──── o_mem_done ──▶ (to cpu_fsm)                │
  │  └──────────────────────┘                                                 │
  │                                                                           │
  ├─── o_state[2:0]                                                           │
  └───────────────────────────────────────────────────────────────────────────┘
```

## State Machine

```
                    ┌─────────────────────────────┐
                    │          IDLE                │◄────────────┐
                    └──┬──────────────────┬───────┘             │
                       │ (STORE)          │ (FETCH/LOAD)        │
                       ▼                  │                     │
                   TX_WREN                │                     │
                   WAIT_WREN              │                     │
                       │                  │                     │
                       ▼                  ▼                     │
                   TX_CMD ◄───────────TX_CMD                    │
                   WAIT_CMD               │                     │
                       │                  │                     │
               ┌───────┴──────┐           │                     │
               │(STORE)       │(R/W)      │                     │
               ▼              ▼           │                     │
           TX_DATA        RX_WAIT─────────┼──→ done ──→ IDLE   │
           WAIT_DATA──────────────────────┼──→ done ──→ IDLE   │
                                          │                     │
                                          └─────────────────────┘
```

## SPI Commands (nvSRAM-compatible)

| Operation | Opcode | Hex | TX payload |
|-----------|--------|-----|------------|
| FETCH | READ | `0x03` | `{0x03, addr}` |
| LOAD | FAST_READ | `0x0B` | `{0x0B, addr}` |
| STORE | WREN + WRITE | `0x06` + `0x02` | `{0x06, 0x00}` then `{0x02, addr}` then `{0x00, wdata}` |

STORE is always preceded by a WREN transaction, as required by nvSRAM protocol.

## Protocol Sequences

### FETCH / LOAD
```
IDLE → TX_CMD → WAIT_CMD → RX_WAIT (wait spi_rx_done) → IDLE
         │         │
         └─ spi_tx_data = {opcode, addr}
                   └─ spi_tx_load pulses
```

### STORE
```
IDLE → TX_WREN → WAIT_WREN → TX_CMD → WAIT_CMD → TX_DATA → WAIT_DATA → IDLE
         │          │           │         │          │          │
         └─ {0x06,0x00}        └─ {0x02,addr}       └─ {0x00,wdata}
                    └─ tx_load            └─ tx_load            └─ tx_load
```

## Dependencies

Uses `dff`, `register`, and `mux` primitives only.

---
[Back to Main](../README.md)
