[Back to Main](../README.md)

# DFF - D Flip-Flop

> **Master-slave D flip-flop built from NAND gates with async reset and enable**

## Modules

### `sr_latch_nand`

Cross-coupled NAND SR latch (active-low inputs).

| Port | Dir | Description |
|------|-----|-------------|
| `Q`, `Qn` | out | Outputs |
| `Sn`, `Rn` | in | Active-low set/reset |

### `dff`

Positive-edge-triggered D flip-flop.

| Port | Dir | Description |
|------|-----|-------------|
| `Q`, `Qn` | out | Outputs |
| `D` | in | Data input |
| `clk` | in | Clock (rising edge) |
| `rst_n` | in | Async active-low reset |
| `en` | in | Enable (hold value when 0) |

## Implementation

- **Master stage**: Transparent when `clk=0`, latches on `clk` rising edge
- **Slave stage**: Transparent when `clk=1`, outputs update after rising edge
- **Enable**: NAND-gate mux feeds back Q when `en=0`
- **Reset**: Async active-low reset on slave latch via extra NAND input
- Gate-level only — no behavioral constructs

## Dependencies

None (leaf cell).

---
[Back to Main](../README.md)
