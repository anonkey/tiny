[Back to Main](../README.md)

# SPI Byte Counter — Byte Boundary Detector

> **4-bit counter tracking 8 SCLK edges per byte, with RX latch and byte_done pulse**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `byte_done` | out | 1 | Pulse (1 sys clk) when 8 bits received |
| `rx_data` | out | 8 | Latched RX byte (updated on byte_done) |
| `rx_shift` | in | 8 | Current RX shift register contents |
| `sclk_rise` | in | 1 | SCLK rising edge pulse |
| `cs_n` | in | 1 | Chip select (active low) |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## Implementation

- 4-bit counter increments on SCLK rising edge while CS active
- Resets to 0 when CS deasserted or count reaches 8
- On count==8: latches `rx_shift` into `rx_data` and pulses `byte_done`
- Incomplete transfers (CS deasserts before 8 bits) are silently discarded

## Dependencies

Uses `dff` and `register` primitives.

---
[Back to Main](../README.md)
