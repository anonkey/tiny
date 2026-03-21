[Back to Main](../README.md)

# Memory Controller - SPI Protocol Handler

> **Translates abstract memory requests into byte-by-byte SPI transactions (nvSRAM-compatible). Drives CS_n to frame variable-length commands.**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `spi_tx_data` | out | 8 | Byte to load into SPI TX shift register |
| `spi_tx_load` | out | 1 | Pulse to trigger SPI TX byte |
| `spi_rx_data` | in | 8 | Byte received from SPI RX |
| `spi_byte_done` | in | 1 | SPI byte complete pulse |
| `cs_n` | out | 1 | Chip select output (active low) |
| `read_data` | out | 16 | Accumulated RX data (instruction or memory byte) |
| `mem_req` | in | 1 | Pulse: start memory operation |
| `mem_op` | in | 2 | Operation: 00=FETCH, 01=LOAD, 10=STORE |
| `mem_addr` | in | 8 | Address |
| `mem_wdata` | in | 8 | Write data (STORE only) |
| `mem_done` | out | 1 | Pulse: operation complete |
| `state` | out | 4 | Current FSM state (debug) |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## State Machine

```
                    ┌──────────────────────────────┐
                    │           IDLE               │◄───────────────────┐
                    └──┬───────────────────┬───────┘                    │
                       │ (STORE)           │ (FETCH/LOAD)               │
                       ▼                   ▼                            │
                  WREN_LOAD           CMD_LOAD                          │
                  WREN_WAIT           CMD_WAIT                          │
                       │                   │                            │
                       ▼                   ▼                            │
                  WREN_CS_HI          ADDR_LOAD                         │
                       │              ADDR_WAIT                         │
                       │         ┌────────┼────────┐                    │
                       │     (STORE)   (LOAD)   (FETCH)                 │
                       │         │        │        │                    │
                       ▼         ▼        ▼        ▼                    │
                  CMD_LOAD  WDATA_LOAD DUMMY_LOAD RX1_LOAD              │
                  CMD_WAIT  WDATA_WAIT DUMMY_WAIT RX1_WAIT              │
                       │         │        │    ┌───┴───┐                │
                       ▼         │        │ (LOAD)  (FETCH)             │
                  ADDR_LOAD      │        ▼        ▼                    │
                  ADDR_WAIT ─────┼── RX1_LOAD  RX2_LOAD                 │
                       │         │   RX1_WAIT  RX2_WAIT                 │
                       ▼         │        │        │                    │
                  WDATA_LOAD     │        ▼        ▼                    │
                  WDATA_WAIT ────┴──→ done ──→ IDLE ──→ done ──→ IDLE  │
                                                                        │
                                       └────────────────────────────────┘
```

## SPI Commands (nvSRAM-compatible, 8-bit byte-by-byte)

| Operation | Opcode | Hex | SPI byte sequence |
|-----------|--------|-----|-------------------|
| FETCH | READ | `0x03` | CS↓ `[0x03] [addr] [rx_hi] [rx_lo]` CS↑ |
| LOAD | FAST_READ | `0x0B` | CS↓ `[0x0B] [addr] [dummy] [rx_byte]` CS↑ |
| STORE | WREN + WRITE | `0x06` + `0x02` | CS↓ `[0x06]` CS↑ then CS↓ `[0x02] [addr] [wdata]` CS↑ |

STORE is always preceded by a WREN transaction (separate CS cycle), as required by nvSRAM protocol.

**Note:** Standard nvSRAM uses 2-byte (≤512Kbit) or 3-byte (≥1Mbit) addressing. This design uses a single address byte, matching the 8-bit CPU address bus (256-byte address space). For larger nvSRAMs, the upper address byte(s) are implicitly zero.

## Protocol Sequences

### FETCH (READ 0x03)
```
IDLE → CMD_LOAD → CMD_WAIT → ADDR_LOAD → ADDR_WAIT → RX1_LOAD → RX1_WAIT → RX2_LOAD → RX2_WAIT → IDLE
         │           │           │           │           │           │           │           │
         └─ tx=0x03  └─ byte_done └─ tx=addr  └─ byte_done └─ tx=0x00  └─ latch hi └─ tx=0x00  └─ latch lo
                                                                                                    mem_done
CS_n:  ↓─────────────────────────────────────────────────────────────────────────────────────────↑
```

### LOAD (FAST_READ 0x0B)
```
IDLE → CMD_LOAD → CMD_WAIT → ADDR_LOAD → ADDR_WAIT → DUMMY_LOAD → DUMMY_WAIT → RX1_LOAD → RX1_WAIT → IDLE
         │           │           │           │             │            │            │           │
         └─ tx=0x0B  └─ byte_done └─ tx=addr  └─ byte_done  └─ tx=0x00   └─ byte_done └─ tx=0x00  └─ latch lo
                                                                                                      mem_done
CS_n:  ↓──────────────────────────────────────────────────────────────────────────────────────────────↑
```

### STORE (WREN + WRITE)
```
IDLE → WREN_LOAD → WREN_WAIT → WREN_CS_HI → CMD_LOAD → CMD_WAIT → ADDR_LOAD → ADDR_WAIT → WDATA_LOAD → WDATA_WAIT → IDLE
         │            │             │            │           │           │           │            │            │
         └─ tx=0x06   └─ byte_done  │            └─ tx=0x02  └─ byte_done └─ tx=addr  └─ byte_done └─ tx=wdata  └─ byte_done
                                    │                                                                               mem_done
CS_n:  ↓──────────────────────────↑ ↓────────────────────────────────────────────────────────────────────────────────↑
```

## Read Data Accumulator

`o_read_data[15:0]` assembles received bytes for the CPU:

| Operation | `read_data[15:8]` | `read_data[7:0]` |
|-----------|-------------------|-------------------|
| FETCH | RX byte 1 (instr hi) | RX byte 2 (instr lo) |
| LOAD | (unchanged) | RX byte 1 (data) |

## Dependencies

`read_data_accum.v`, `dff.v`, `register.v`, `mux.v`

---
[Back to Main](../README.md)
