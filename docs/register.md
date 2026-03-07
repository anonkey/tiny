[Back to Main](../README.md)

# Register - N-bit Register

> **Parameterized register built from N D flip-flops**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `Q` | out | N | Stored value |
| `D` | in | N | Data input |
| `clk` | in | 1 | Clock (rising edge) |
| `rst_n` | in | 1 | Async active-low reset |
| `en` | in | 1 | Enable (hold when 0) |

| Parameter | Default | Description |
|-----------|---------|-------------|
| `N` | 8 | Bit width |

## Implementation

`generate` loop instantiating N `dff` modules, one per bit. Each DFF has independent async reset and shared enable/clock.

## Dependencies

`dff.v`

---
[Back to Main](../README.md)
