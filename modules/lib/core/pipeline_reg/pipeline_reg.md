[Back to Main](../README.md)

# Pipeline Register — Conditional Latch

> **Parameterized register that latches input when condition is true, holds otherwise**

## Modules

### `pipeline_reg`

N-bit conditional latch using `register` primitive.

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `Q` | out | N | Stored value |
| `D` | in | N | Data input |
| `latch` | in | 1 | When high, capture D; when low, hold Q |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

| Parameter | Default | Description |
|-----------|---------|-------------|
| `N` | 8 | Register width |

### `pipeline_dff`

1-bit variant using `dff` primitive. Same interface as `pipeline_reg` with N=1.

## Usage

Used in `cpu_fsm` to latch datapath values (ALU result, rs2 data, is_load, is_store) during the EXECUTE stage and hold them for subsequent pipeline stages.

## Dependencies

Uses `dff` and `register` primitives.

---
[Back to Main](../README.md)
