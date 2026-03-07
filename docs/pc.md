[Back to Main](../README.md)

# PC - Program Counter

> **8-bit program counter with increment (Kogge-Stone) and jump load**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `pc_out` | out | 8 | Current PC value |
| `load_addr` | in | 8 | Jump target address |
| `load` | in | 1 | 1=load address, 0=increment |
| `clk` | in | 1 | Clock |
| `rst_n` | in | 1 | Async active-low reset |

## Implementation

```
PC+1 ──┐
       MUX ── register ── pc_out
load ──┘         ↑
                clk, rst_n
```

- **Increment**: Kogge-Stone adder computes `pc_out + 1`
- **Jump**: 2:1 mux selects between `pc_out + 1` and `load_addr`
- **Storage**: 8-bit register (8 DFFs) holds current PC, resets to 0

## Dependencies

`kogge-stone.v`, `mux.v`, `register.v`

---
[Back to Main](../README.md)
