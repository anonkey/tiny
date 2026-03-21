[Back to Main](../README.md)

# CDC Sync — Clock Domain Crossing Synchronizer + Edge Detector

> **Parameterized N-stage FF synchronizer for safely crossing clock domains, plus a rising/falling edge detector**

## Modules

### `cdc_sync`

N-stage flip-flop chain for synchronizing an asynchronous signal into a clock domain.

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `sync` | out | 1 | Synchronized output |
| `async` | in | 1 | Asynchronous input signal |
| `clk` | in | 1 | Destination clock domain |
| `rst_n` | in | 1 | Async active-low reset |

| Parameter | Default | Description |
|-----------|---------|-------------|
| `STAGES` | 2 | Number of synchronizer stages (2 minimum for MTBF) |

### `edge_detect`

Detects rising and falling edges of a (already synchronized) signal by comparing against a 1-clock delayed copy.

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `rise` | out | 1 | High for one clock on rising edge |
| `fall` | out | 1 | High for one clock on falling edge |
| `sync` | in | 1 | Synchronized input signal |
| `clk` | in | 1 | Clock |
| `rst_n` | in | 1 | Async active-low reset |

## Usage

```verilog
cdc_sync #(.STAGES(3)) sclk_sync (
  .o_sync(w_sclk_sync), .i_async(i_sclk),
  .i_clk(i_clk), .i_rst_n(i_rst_n)
);

edge_detect sclk_edge (
  .o_rise(w_rise), .o_fall(w_fall),
  .i_sync(w_sclk_sync),
  .i_clk(i_clk), .i_rst_n(i_rst_n)
);
```

## Dependencies

Uses `dff` primitive.

---
[Back to Main](../README.md)
