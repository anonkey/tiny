# Assembler

> **Converts human-readable assembly to hex files for the CPU ROM**

## Usage

```bash
python tools/assembler.py program.asm -o program.hex
python tools/assembler.py program.asm -o program.hex -v   # verbose listing
python tools/assembler.py program.asm -d 128              # custom ROM depth
```

## Assembly Syntax

### Instructions

```asm
; R-type: op rd, rs1, rs2
ADD  r2, r0, r1     ; r2 = r0 + r1
SUB  r4, r2, r3     ; r4 = r2 - r3
AND  r7, r5, r6     ; r7 = r5 & r6
OR   r0, r5, r6     ; r0 = r5 | r6
XOR  r1, r5, r6     ; r1 = r5 ^ r6
NAND r0, r1, r2     ; r0 = ~(r1 & r2)
NOR  r0, r1, r2     ; r0 = ~(r1 | r2)
XNOR r0, r1, r2     ; r0 = ~(r1 ^ r2)

; U-type: op rd, rs1
NOT  r3, r2         ; r3 = ~r2

; I-type: op rd, rs1, imm6
ADDI r1, r0, 5      ; r1 = r0 + 5 (signed -32..31)

; L-type: op rd, imm8
LDI  r0, 42         ; r0 = 42 (0..255)

; Control flow
JMP  label           ; jump to label
JMP  20              ; jump to address 20
BEQ  label           ; branch if zero flag set
NOP                  ; no operation
```

### Labels

```asm
loop:                ; define label at current address
    ADDI r0, r0, 1
    JMP loop         ; reference label
```

### Number Formats

```asm
42                   ; decimal
0x2A                 ; hexadecimal
0b101010             ; binary
```

### Comments

```asm
LDI r0, 10          ; everything after semicolon is a comment
```

## Output Format

One 16-bit hex value per line, padded to ROM depth (default 256) with NOPs:

```
A014
A228
0408
...
F000
```

## Options

| Flag | Description |
|------|-------------|
| `-o FILE` | Output file (default: stdout) |
| `-d N` | ROM depth, pads with NOPs (default: 256) |
| `-v` | Print listing with addresses and hex |
