[Back to Main](../README.md)

# Decoder - Instruction Decoder

> **Extracts instruction fields and generates control signals for the CPU datapath**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `instr` | in | 16 | Raw instruction word |
| `alu_op` | out | 4 | ALU operation code |
| `rd` | out | 3 | Destination register |
| `rs1` | out | 3 | Source register 1 |
| `rs2` | out | 3 | Source register 2 |
| `imm8` | out | 8 | 8-bit immediate (LDI, JMP, BEZ) |
| `imm6` | out | 6 | 6-bit immediate (ADDI, LOAD, STORE) |
| `reg_we` | out | 1 | Register file write enable |
| `alu_src` | out | 1 | ALU operand B select: 0=rs2, 1=imm6 |
| `pc_load` | out | 1 | Load PC (JMP) |
| `use_imm8` | out | 1 | Writeback select: 1=imm8, 0=ALU result |

## Field Extraction

```
instr[15:12] → opcode
instr[11:9]  → rd (or rs1 for BEZ)
instr[8:6]   → rs1
instr[5:3]   → rs2
instr[5:0]   → imm6
instr[8:1]   → imm8
```

## Control Signal Logic

| Opcode | `reg_we` | `alu_src` | `pc_load` | `use_imm8` | `alu_op` |
|--------|----------|-----------|-----------|------------|----------|
| ADD-NOT (0-5) | 1 | 0 | 0 | 0 | opcode |
| Unused (6-7) | 0 | 0 | 0 | 0 | opcode |
| Reserved (8) | 0 | 0 | 0 | 0 | - |
| ADDI (9) | 1 | 1 | 0 | 0 | 0000 (ADD) |
| LDI (A) | 1 | 0 | 0 | 1 | - |
| JMP (B) | 0 | 0 | 1 | 0 | - |
| BEZ (C) | 0 | 0 | 0 | 0 | 0000 (ADD) |
| LOAD (D) | 1 | 1 | 0 | 0 | 0000 (ADD) |
| STORE (E) | 0 | 1 | 0 | 0 | 0000 (ADD) |
| NOP (F) | 0 | 0 | 0 | 0 | - |

ADDI, BEZ, LOAD, and STORE remap `alu_op` to `0000` (ADD). For BEZ, the CPU forces ALU operand B to zero, so ALU computes rs1 + 0 = rs1; zero flag reflects rs1 == 0.

## Dependencies

None (pure combinational logic).

---
[Back to Main](../README.md)
