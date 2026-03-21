[Back to Main](../README.md)

# ROM - Read-Only Memory

> **Parameterized ROM initialized from a hex file at elaboration time**

## Interface

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `data` | out | WIDTH | Read data |
| `addr` | in | log2(DEPTH) | Address |

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DEPTH` | 256 | Number of entries |
| `WIDTH` | 16 | Bits per entry |
| `MEMFILE` | `""` | Hex file path for `$readmemh` |

## Implementation

- `reg` array + `assign data = mem[addr]` for combinational read
- `initial $readmemh(MEMFILE, mem)` loads contents at elaboration
- This is the only module using `reg` and `initial` — standard synthesizable ROM pattern

## Usage in CPU

Instruction memory: 256 entries x 16 bits, addressed by the 8-bit program counter.

```verilog
rom #(.DEPTH(256), .WIDTH(16), .MEMFILE("program.hex")) imem (
   .data(instr),
   .addr(pc_out)
);
```

## Dependencies

None.

---
[Back to Main](../README.md)
