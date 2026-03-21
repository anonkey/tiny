[Back to Main](../README.md)

# Writeback Mux — Register File Write Data Selector

> **3-way mux selecting the source for register file writeback in half_cpu**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `write_data` | out | 8 | Selected write data for register file |
| `alu_result` | in | 8 | ALU computation result |
| `imm8` | in | 8 | 8-bit immediate (LDI) |
| `load_data` | in | 8 | Data loaded from memory (LOAD) |
| `use_imm8` | in | 1 | Select imm8 (LDI instruction) |
| `load_data_sel` | in | 1 | Select load_data (LOAD instruction, priority) |

## Selection Logic

| Priority | Condition | Select | Source |
|----------|-----------|--------|--------|
| 1 | `load_data_sel` | 2 | Memory load data |
| 2 | `use_imm8` | 1 | 8-bit immediate |
| 3 | default | 0 | ALU result |

## Dependencies

Uses `mux` primitive.

---
[Back to Main](../README.md)
