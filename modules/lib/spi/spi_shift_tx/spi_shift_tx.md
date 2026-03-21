[Back to Main](../README.md)

# SPI Shift TX — Transmit Shift Register

> **8-bit MSB-first TX shift register with load guard for SPI MISO output**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `miso` | out | 1 | MISO output (shift[7] when active, 0 otherwise) |
| `data` | in | 8 | Byte to transmit |
| `load` | in | 1 | Pulse to parallel-load data |
| `shift_en` | in | 1 | Shift left enable (SCLK falling edge & CS active) |
| `active` | in | 1 | CS active flag (active high) |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## Implementation

- Parallel load on `load`, left-shift on `shift_en`
- 1-clock guard after load suppresses stale shift_en from the SCLK synchronizer's delayed falling edge
- MISO outputs MSB when active, 0 when idle

## Dependencies

Uses `dff` and `register` primitives.

---
[Back to Main](../README.md)
