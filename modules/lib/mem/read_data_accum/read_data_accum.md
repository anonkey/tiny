[Back to Main](../README.md)

# Read Data Accumulator — Multi-Byte RX Assembler

> **Assembles 16-bit word from individual SPI RX bytes (high and low byte latches)**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `read_data` | out | 16 | Assembled word: {hi_byte, lo_byte} |
| `rx_byte` | in | 8 | Incoming RX byte |
| `latch_hi` | in | 1 | Latch rx_byte into high byte register |
| `latch_lo` | in | 1 | Latch rx_byte into low byte register |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## Usage by mem_ctrl

| Operation | High byte | Low byte |
|-----------|-----------|----------|
| FETCH | RX byte 1 (instr hi) | RX byte 2 (instr lo) |
| LOAD | (unchanged) | RX byte 1 (data) |

## Dependencies

Uses `register` primitive.

---
[Back to Main](../README.md)
