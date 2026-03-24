[Back to Main](../README.md)

# CPU FSM - Pipeline State Machine Controller

> **Orchestrates instruction fetch, decode, execute, memory access, and writeback via abstract memory bus**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `mem_req` | out | 1 | Pulse to request memory operation |
| `mem_op` | out | 2 | Operation: 00=FETCH, 01=LOAD, 10=STORE |
| `mem_addr` | out | 8 | Address for memory operation |
| `mem_wdata` | out | 8 | Write data (STORE only) |
| `mem_done` | in | 1 | Pulse when memory operation completes |
| `instr_en` | out | 1 | Latch instruction from memory data |
| `reg_we` | out | 1 | Enable regfile write |
| `pc_en` | out | 1 | Enable PC advance |
| `load_data_sel` | out | 1 | 1 = writeback from memory (LOAD) |
| `state` | out | 3 | Current FSM state (debug) |
| `pc` | in | 8 | Current program counter |
| `alu_result` | in | 8 | ALU output (memory address for LOAD/STORE) |
| `rs2_data` | in | 8 | Register source 2 (STORE data) |
| `is_load` | in | 1 | Decoder indicates LOAD instruction |
| `is_store` | in | 1 | Decoder indicates STORE instruction |
| `timeout` | in | 1 | SPI timeout pulse from mem_ctrl |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Async active-low reset |

## State Machine

```
FETCH_REQ → FETCH_WAIT → DECODE → EXECUTE
                                      │
                        ┌─────────────┼──────────────┐
                        │ (normal)    │ (LOAD/STORE) │
                        ▼             ▼              │
                    WRITEBACK     MEM_REQ            │
                        │         MEM_WAIT           │
                        │             │              │
                        ▼             ▼              │
                    PC_UPDATE ◄── WRITEBACK          │
                        │                            │
                        └──→ FETCH_REQ (loop)        │
```

## Memory Operations

| Operation | `mem_op` | Address source | Data |
|-----------|----------|---------------|------|
| FETCH | `00` | PC | — (reads instruction) |
| LOAD | `01` | ALU result | — (reads data) |
| STORE | `10` | ALU result | rs2_data |

The CPU FSM issues abstract memory requests. The memory controller (`mem_ctrl`) translates them into SPI transactions.

## Timeout Recovery

On `i_timeout` from `mem_ctrl`, both `FETCH_WAIT` and `MEM_WAIT` transition to `FETCH_REQ`, restarting the pipeline from fetch.

## Dependencies

`pipeline_reg.v`, `dff.v`, `register.v`

---
[Back to Main](../README.md)
