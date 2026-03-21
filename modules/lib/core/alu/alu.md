[Back to Main](../README.md)

# ALU - Arithmetic Logic Unit

> **6-operation 8-bit ALU using a Kogge-Stone adder for arithmetic**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `result` | out | 8 | Operation result |
| `carry` | out | 1 | Carry out (ADD/SUB only) |
| `a` | in | 8 | Operand A |
| `b` | in | 8 | Operand B |
| `opcode` | in | 4 | Operation select |

## Operations

| Opcode | Mnemonic | Result |
|--------|----------|--------|
| `0000` | ADD | `a + b` |
| `0001` | SUB | `a - b` |
| `0010` | AND | `a & b` |
| `0011` | OR | `a \| b` |
| `0100` | XOR | `a ^ b` |
| `0101` | NOT | `~a` |

## Implementation

- ADD/SUB share a single `kogge_stone` instance; `opcode[0]` selects subtraction (two's complement via XOR + carry-in)
- All 6 results are computed in parallel, then a 16:1 mux selects the output based on `opcode`
- Carry flag is only valid for ADD (`0000`) and SUB (`0001`)
- Purely dataflow — no `always` blocks

## Dependencies

`kogge-stone.v`, `mux.v`

---
[Back to Main](../README.md)
