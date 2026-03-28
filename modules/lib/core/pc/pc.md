[Back to Main](../README.md)

# PC - Program Counter

> **8-bit program counter with increment (half-adder chain) and jump load**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `o_pc` | out | 8 | Current PC value |
| `i_load_addr` | in | 8 | Jump target address |
| `i_load` | in | 1 | 1=load address, 0=increment |
| `i_en` | in | 1 | PC update enable |
| `i_clk` | in | 1 | Clock |
| `i_rst_n` | in | 1 | Async active-low reset |

## Implementation

```
PC+1 ──┐
       MUX ── register ── pc_out
load ──┘         ↑
                clk, rst_n
```

- **Increment**: `pc_inc` half-adder chain computes `pc_out + 1`
- **Jump**: 2:1 mux selects between `pc_out + 1` and `load_addr`
- **Storage**: 8-bit register (8 DFFs) holds current PC, resets to 0

## Dependencies

`pc_inc`, `mux`, `register` (+ `dff` transitively)

---
[Back to Main](../README.md)
