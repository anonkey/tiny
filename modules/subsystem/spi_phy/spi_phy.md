[Back to Main](../README.md)

# SPI PHY - 8-bit Byte-Oriented Half-Duplex

> **SPI PHY with 8-bit TX (MISO) and RX (MOSI) shift registers, clock domain synchronizers, and byte_done pulse every 8 SCLK edges**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `rx_data` | out | 8 | Last received 8-bit byte |
| `byte_done` | out | 1 | Pulse (1 sys clk) when 8 bits received |
| `tx_data` | in | 8 | Byte to transmit on MISO |
| `tx_load` | in | 1 | Pulse to load TX shift register |
| `miso` | out | 1 | SPI master-in slave-out |
| `sclk` | in | 1 | SPI clock (from master, asynchronous) |
| `mosi` | in | 1 | SPI master-out slave-in |
| `cs_n` | in | 1 | Chip select (active low, driven synchronously by mem_ctrl) |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## Protocol

8-bit byte-oriented, half-duplex. `mem_ctrl` drives CS_n to frame variable-length transactions.

```
Single byte transfer:
  CS_n low → 8 SCLK edges → byte_done pulse → CS_n stays low for next byte or goes high

Multi-byte within one CS assertion:
  CS_n low → [byte1] → byte_done → [byte2] → byte_done → ... → CS_n high
```

### Timing Diagram

```
         Byte 1                    Byte 2
    ┌──────────────────┐      ┌──────────────────┐
CS_n ──┘                  └──────┘                  └──────
SCLK    _/‾\_/‾\_ ... _/‾\_      _/‾\_/‾\_ ... _/‾\_
MISO    [b7..............b0]      [b7..............b0]
MOSI    [b7..............b0]      [b7..............b0]
         ←── 8 bits ──→           ←── 8 bits ──→
```

## Implementation

Composed from reusable sub-modules:

- **`cdc_sync`** (3-stage): Synchronizes SCLK into system clock domain.
- **`cdc_sync`** (2-stage): Synchronizes MOSI. CS_n is synchronous (driven by mem_ctrl), no synchronizer needed.
- **`edge_detect`**: Derives rising/falling edge pulses from synchronized SCLK.
- **`spi_shift_tx`**: 8-bit TX shift register with load guard. Shifts MSB-first on SCLK falling edge.
- **`spi_shift_rx`**: 8-bit RX shift register. Captures MOSI on SCLK rising edge, MSB-first.
- **`spi_byte_counter`**: 4-bit counter tracks bit position, auto-resets at 8. Latches RX data and pulses `byte_done`.
- **Multi-byte**: Counter auto-resets at 8, allowing back-to-back bytes within a single CS assertion.
- Incomplete transfers (CS deasserts before 8 bits) are silently discarded.

## Dependencies

`cdc_sync.v`, `spi_shift_tx.v`, `spi_shift_rx.v`, `spi_byte_counter.v`, `dff.v`, `register.v`

---
[Back to Main](../README.md)
