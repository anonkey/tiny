## How it works

8-bit single-cycle CPU executing 16-bit instructions from a 256-entry ROM.

- 16 opcodes: arithmetic (ADD, SUB, ADDI), logic (AND, OR, XOR, NOT, NAND, NOR, XNOR), load immediate (LDI), control flow (JMP, BEQ, NOP)
- 8 general-purpose 8-bit registers
- Kogge-Stone parallel prefix adder for fast arithmetic
- Built entirely from dataflow (`assign`) and structural (module instantiation) Verilog — no `always` blocks

Outputs:
- `uo_out[7:0]` : ALU result
- `uio_out[7:0]` : Program counter

## How to test

Program is loaded from `program.hex` into ROM at synthesis time.

```
source .venv/bin/activate
make -f Makefile.cpu
```

## External hardware

No external hardware required. Observe ALU result on `uo_out` and program counter on `uio_out`.
