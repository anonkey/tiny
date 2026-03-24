[Back to Main](../README.md)

# Regfile - Register File

> **8x8-bit register file with 2 read ports and 1 write port; r0 hardwired to zero**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `rd1` | out | 8 | Read port 1 data |
| `rd2` | out | 8 | Read port 2 data |
| `wd` | in | 8 | Write data |
| `raddr1` | in | 3 | Read address 1 |
| `raddr2` | in | 3 | Read address 2 |
| `waddr` | in | 3 | Write address |
| `we` | in | 1 | Write enable |
| `clk` | in | 1 | Clock |
| `rst_n` | in | 1 | Async active-low reset |

| Parameter | Default | Description |
|-----------|---------|-------------|
| `NREG` | 8 | Number of registers |
| `WIDTH` | 8 | Bits per register |

## Implementation

```
         ┌── demux ── we[0] ──(masked 0)── reg[0] ──┐
we ──────┤   ...                                      ├── mux ── rd1
waddr ───┘── demux ── we[7] ────────────── reg[7] ──┤
                                                      └── mux ── rd2
```

- **Write decode**: Demux routes `we` to the selected register based on `waddr`
- **r0 protection**: Write-enable for r0 is permanently tied low; r0 always reads zero
- **Registers**: 8 instances of `register #(.N(8))`, each built from 8 DFFs
- **Read ports**: Two independent muxes (8:1, 8-bit) select register outputs
- Reads are combinational (async), writes are clocked (rising edge)

## Dependencies

`register.v`, `mux.v` (mux + demux)

---
[Back to Main](../README.md)
