[Back to Main](../README.md)

# SPI Shift RX — Receive Shift Register

> **8-bit MSB-first RX shift register for SPI MOSI input**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `data` | out | 8 | Current shift register contents |
| `bit` | in | 1 | Input bit (synchronized MOSI) |
| `shift_en` | in | 1 | Shift enable (SCLK rising edge & CS active) |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## Implementation

Shifts in `bit` at LSB on each `shift_en`, MSB-first. Output is the raw shift register — byte boundary detection is handled by `spi_byte_counter`.

## Dependencies

Uses `register` primitive.

---
[Back to Main](../README.md)
