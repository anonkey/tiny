# Cocotb Helpers

> **Shared test utilities for cocotb-based simulation tests**

## Usage

```python
from cocotb_helpers import start_clock, reset_sync, tick, wait_for
from cocotb_helpers import spi_send_8, spi_recv_8, spi_clock_byte
from cocotb_helpers import enc_r, enc_imm6, enc_imm8, enc_bez
from cocotb_helpers import OP_ADD, OP_SUB, OP_BEZ, OP_NOP
```

## Modules

### clock_reset

| Function | Description |
|----------|-------------|
| `start_clock(dut, period_ns=10)` | Start system clock, returns forked coroutine |
| `reset_sync(dut, clk_cycles=3)` | Synchronous reset: hold `rst_n` low for N rising edges |
| `reset_async(dut, hold_ns=10)` | Asynchronous reset: hold `rst_n` low for a fixed time |

### timing

| Function | Description |
|----------|-------------|
| `tick(dut, n=1)` | Advance N full clock cycles |
| `wait_for(dut, signal, value=1, timeout=50)` | Poll signal on rising edges until match, raise `TimeoutError` on timeout |

### spi

| Function | Description |
|----------|-------------|
| `spi_send_8(dut, value, half_period_ns=50)` | Master sends 8 bits via MOSI (Timer-based SCLK) |
| `spi_recv_8(dut, half_period_ns=50)` | Master receives 8 bits via MISO (Timer-based SCLK) |
| `spi_clock_byte(dut, tx_byte=0x00, sclk_div=5)` | Clock one SPI byte using system-clock-derived SCLK |

SPI command constants: `CMD_IFETCH` (0x03), `CMD_LOAD` (0x0B), `CMD_STORE` (0x02), `CMD_WREN` (0x06).

### isa

Opcode constants:

```
OP_ADD (0000)  OP_SUB (0001)  OP_AND (0010)  OP_OR  (0011)
OP_XOR (0100)  OP_NOT (0101)  OP_ADDI(1001)  OP_LDI (1010)
OP_JMP (1011)  OP_BEZ (1100)  OP_LOAD(1101)  OP_STORE(1110)
OP_NOP (1111)
```

| Function | Description |
|----------|-------------|
| `enc_r(opcode, rd, rs1, rs2)` | Encode R-type: `[opcode:4][rd:3][rs1:3][rs2:3][unused:3]` |
| `enc_imm6(opcode, rd, rs1, imm6)` | Encode I-type: `[opcode:4][rd:3][rs1:3][imm6:6]` |
| `enc_imm8(opcode, rd, imm8)` | Encode L-type: `[opcode:4][rd:3][imm8:8][0]` |
| `enc_bez(rs1, imm8)` | Encode BEZ: `[1100][rs1:3][imm8:8][0]` (rs1 in rd slot) |
