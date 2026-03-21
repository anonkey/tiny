[Back to Main](../README.md)

# ALU Operand Mux — Operand B Selector

> **Selects ALU operand B between rs2 register data and sign-extended 6-bit immediate**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `alu_b` | out | 8 | Selected operand B |
| `rs2_data` | in | 8 | Register source 2 data |
| `imm6` | in | 6 | 6-bit immediate (sign-extended to 8 bits) |
| `sel` | in | 1 | 0 = rs2_data, 1 = sign-extended imm6 |
| `clk` | in | 1 | System clock (unused, for interface consistency) |
| `rst_n` | in | 1 | Reset (unused, for interface consistency) |

## Sign Extension

`imm6[5]` is replicated into bits [7:6] to produce an 8-bit signed value:
```
imm6 = 6'b100001 (-31) → 8'b11100001 (-31)
imm6 = 6'b011111 (+31) → 8'b00011111 (+31)
```

## Usage

Shared by both `cpu.v` and `half_cpu.v` to eliminate duplicated operand selection logic.

## Dependencies

Uses `mux` primitive.

---
[Back to Main](../README.md)
