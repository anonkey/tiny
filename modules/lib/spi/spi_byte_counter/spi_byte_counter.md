[Back to Main](../README.md)

# SPI Byte Counter — Byte Boundary Detector

> **Parameterizable counter tracking BYTE_WIDTH SCLK edges per byte, with RX latch and byte_done pulse**

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BYTE_WIDTH` | 8 | Number of SCLK edges per byte (data width) |

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `byte_done` | out | 1 | Pulse (1 sys clk) when BYTE_WIDTH bits received |
| `rx_data` | out | BYTE_WIDTH | Latched RX byte (updated on byte_done) |
| `rx_shift` | in | BYTE_WIDTH | Current RX shift register contents |
| `sclk_rise` | in | 1 | SCLK rising edge pulse |
| `cs_n` | in | 1 | Chip select (active low) |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## Implementation

- Counter width is `$clog2(BYTE_WIDTH + 1)`, sized automatically
- Counter increments on SCLK rising edge while CS active
- Resets to 0 when CS deasserted or count reaches BYTE_WIDTH
- On count==BYTE_WIDTH: latches `rx_shift` into `rx_data` and pulses `byte_done`
- Incomplete transfers (CS deasserts before BYTE_WIDTH bits) are silently discarded

## Dependencies

Uses `dff` and `register` primitives.

---
[Back to Main](../README.md)
