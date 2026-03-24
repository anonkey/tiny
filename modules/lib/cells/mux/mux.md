[Back to Main](../README.md)

# MUX / DEMUX - Parameterized Multiplexer and Demultiplexer

> **Recursive tree-structured mux and demux with configurable width and ways**

## Modules

### `mux`

N-to-1 multiplexer.

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `in` | in | WAY * WIRE | Concatenated inputs |
| `ctrl` | in | log2(WAY) | Selection |
| `out` | out | WIRE | Selected output |

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WAY` | 8 | Number of input channels |
| `WIRE` | 1 | Bit width per channel |

### `demux`

1-to-N demultiplexer.

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `in` | in | WIRE | Input data |
| `ctrl` | in | log2(WAY) | Channel select |
| `out` | out | WAY * WIRE | Routed output (others = 0) |

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WAY` | 8 | Number of output channels |
| `WIRE` | 1 | Bit width per channel |

## Implementation

Recursive binary tree — splits in half at each level until `WAY=2`, then a simple ternary select. Purely combinational.

**Constraint:** `WAY` must be a power of 2. A compile-time guard triggers an elaboration error (`NON_POWER_OF_2_WAY`) if violated.

## Usage in CPU

- ALU result mux (16:1, 8-bit)
- ALU operand B mux (2:1, 8-bit)
- Writeback mux (2:1, 8-bit)
- PC next mux (2:1, 8-bit)
- Regfile read ports (8:1, 8-bit)
- Regfile write-enable demux (1:8, 1-bit)

## Dependencies

None (leaf module).

---
[Back to Main](../README.md)
