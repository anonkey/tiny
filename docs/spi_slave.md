[Back to Main](../README.md)

# SPI Slave - Two-Phase Half-Duplex 16-bit

> **SPI slave with TX (MISO) and RX (MOSI) shift registers, clock domain synchronizers, and cmd+addr protocol support**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `rx_data` | out | 16 | Last received 16-bit word |
| `rx_done` | out | 1 | Pulse (1 sys clk) when valid RX completes |
| `tx_data` | in | 16 | Data to transmit on MISO |
| `tx_load` | in | 1 | Pulse to load TX shift register |
| `miso` | out | 1 | SPI master-in slave-out |
| `sclk` | in | 1 | SPI clock (from master) |
| `mosi` | in | 1 | SPI master-out slave-in |
| `cs_n` | in | 1 | Chip select (active low) |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## Protocol

Two-phase half-duplex with `{cmd, addr}` framing:

```
Phase 1 — TX (chip → master):
  CS_n low → 16 SCLK edges → MISO = {cmd[7:0], addr[7:0]} → CS_n high

Phase 2 — RX (master → chip):
  CS_n low → 16 SCLK edges → MOSI = data[15:0] → CS_n high
```

### Commands

| Cmd | Hex | Description |
|-----|-----|-------------|
| IFETCH | `0x01` | Instruction fetch — addr = PC |
| LOAD | `0x02` | Memory read — addr = memory address |
| STORE | `0x03` | Memory write — addr = memory address |

### Timing Diagram

```
         Phase 1 (TX)                    Phase 2 (RX)
    ┌──────────────────┐            ┌──────────────────┐
CS_n ──┘                  └────────────┘                  └──────
SCLK    _/‾\_/‾\_ ... _/‾\_          _/‾\_/‾\_ ... _/‾\_
MISO    [cmd7..cmd0|addr7..addr0]     (don't care)
MOSI    (don't care)                  [d15..............d0]
         ←── 16 bits ──→              ←── 16 bits ──→
```

## Implementation

- **Clock domain crossing**: SCLK, MOSI, and CS_n each pass through a 2-stage FF synchronizer into the system clock domain
- **Edge detection**: rising/falling edges of synchronized SCLK and CS_n derived from delayed copies
- **TX**: shift register loaded via `tx_load`, shifts out MSB-first on SCLK falling edge (data stable for master to sample on rising edge). MISO outputs `r_tx_shift[15]` when CS active, `0` when idle
- **RX**: shift register captures MOSI on SCLK rising edge, MSB-first. 5-bit counter tracks bit position. On CS_n rising edge, if counter == 16, latches `rx_data` and pulses `rx_done`
- Incomplete transfers (CS_n deasserts before 16 bits) are silently discarded

## Dependencies

None (standalone module).

---
[Back to Main](../README.md)
