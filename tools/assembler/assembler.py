#!/usr/bin/env python3
"""Assembler for the tiny CPU.

Usage:
    python assembler.py program.asm -o program.hex

Assembly syntax:
    ADD  r2, r0, r1     ; r2 = r0 + r1
    SUB  r4, r2, r3     ; r4 = r2 - r3
    AND  r7, r5, r6     ; r7 = r5 & r6
    OR   r0, r5, r6     ; r0 = r5 | r6
    XOR  r1, r5, r6     ; r1 = r5 ^ r6
    NOT  r3, r2         ; r3 = ~r2
    ADDI r1, r0, 5      ; r1 = r0 + 5 (imm6, signed -32..31)
    LDI  r0, 42         ; r0 = 42 (imm8, 0..255)
    JMP  label           ; jump to label
    JMP  20              ; jump to address 20
    BEZ  r1, label       ; branch to label if r1 == 0
    BEZ  r1, 10          ; branch to address 10 if r1 == 0
    NOP                  ; no operation

Labels:
    loop:                ; define label at current address
    JMP loop             ; reference label

Numbers:
    42                   ; decimal
    0x2A                 ; hexadecimal
    0b101010             ; binary
"""

import argparse
import sys
import re

OPCODES = {
    "ADD":  0b0000,
    "SUB":  0b0001,
    "AND":  0b0010,
    "OR":   0b0011,
    "XOR":  0b0100,
    "NOT":  0b0101,
    "ADDI": 0b1001,
    "LDI":  0b1010,
    "JMP":  0b1011,
    "BEZ":  0b1100,
    "NOP":  0b1111,
}

R_TYPE = {"ADD", "SUB", "AND", "OR", "XOR"}
I_TYPE = {"ADDI"}
L_TYPE = {"LDI", "JMP"}
U_TYPE = {"NOT"}
N_TYPE = {"NOP"}


def parse_int(s):
    s = s.strip()
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    if s.startswith("0b") or s.startswith("0B"):
        return int(s, 2)
    return int(s)


def parse_reg(s):
    s = s.strip().lower()
    if not s.startswith("r"):
        raise ValueError(f"Expected register (r0-r7), got '{s}'")
    n = int(s[1:])
    if n < 0 or n > 7:
        raise ValueError(f"Register out of range: {s}")
    return n


def encode_r_type(opcode, rd, rs1, rs2):
    return (opcode << 12) | (rd << 9) | (rs1 << 6) | (rs2 << 3)


def encode_i_type(opcode, rd, rs1, imm6):
    if imm6 < -32 or imm6 > 31:
        raise ValueError(f"Immediate {imm6} out of range for 6-bit signed (-32..31)")
    return (opcode << 12) | (rd << 9) | (rs1 << 6) | (imm6 & 0x3F)


def encode_l_type(opcode, rd, imm8):
    if imm8 < 0 or imm8 > 255:
        raise ValueError(f"Immediate {imm8} out of range for 8-bit (0..255)")
    return (opcode << 12) | (rd << 9) | ((imm8 & 0xFF) << 1)


def assemble(source):
    lines = source.splitlines()
    labels = {}
    instructions = []

    # Pass 1: collect labels and count instructions
    addr = 0
    for lineno, line in enumerate(lines, 1):
        # Strip comments
        line = line.split(";")[0].strip()
        if not line:
            continue

        # Label definition
        if line.endswith(":"):
            label = line[:-1].strip()
            if label in labels:
                raise ValueError(f"Line {lineno}: duplicate label '{label}'")
            labels[label] = addr
            continue

        instructions.append((lineno, addr, line))
        addr += 1

    # Pass 2: encode instructions
    machine_code = []

    for lineno, addr, line in instructions:
        parts = re.split(r"[,\s]+", line)
        parts = [p for p in parts if p]
        mnemonic = parts[0].upper()

        if mnemonic not in OPCODES:
            raise ValueError(f"Line {lineno}: unknown instruction '{mnemonic}'")

        opcode = OPCODES[mnemonic]

        try:
            if mnemonic in R_TYPE:
                if len(parts) != 4:
                    raise ValueError(f"Expected: {mnemonic} rd, rs1, rs2")
                rd = parse_reg(parts[1])
                rs1 = parse_reg(parts[2])
                rs2 = parse_reg(parts[3])
                word = encode_r_type(opcode, rd, rs1, rs2)

            elif mnemonic in U_TYPE:
                if len(parts) != 3:
                    raise ValueError(f"Expected: NOT rd, rs1")
                rd = parse_reg(parts[1])
                rs1 = parse_reg(parts[2])
                word = encode_r_type(opcode, rd, rs1, 0)

            elif mnemonic in I_TYPE:
                if len(parts) != 4:
                    raise ValueError(f"Expected: ADDI rd, rs1, imm6")
                rd = parse_reg(parts[1])
                rs1 = parse_reg(parts[2])
                imm = parse_int(parts[3])
                word = encode_i_type(opcode, rd, rs1, imm)

            elif mnemonic == "LDI":
                if len(parts) != 3:
                    raise ValueError(f"Expected: LDI rd, imm8")
                rd = parse_reg(parts[1])
                imm = parse_int(parts[2])
                word = encode_l_type(opcode, rd, imm)

            elif mnemonic == "JMP":
                if len(parts) != 2:
                    raise ValueError(f"Expected: JMP target")
                target = parts[1]
                if target in labels:
                    imm = labels[target]
                else:
                    imm = parse_int(target)
                word = encode_l_type(opcode, 0, imm)

            elif mnemonic == "BEZ":
                if len(parts) != 3:
                    raise ValueError(f"Expected: BEZ rs1, target")
                rs1 = parse_reg(parts[1])
                target = parts[2]
                if target in labels:
                    imm = labels[target]
                else:
                    imm = parse_int(target)
                word = encode_l_type(opcode, rs1, imm)

            elif mnemonic == "NOP":
                if len(parts) != 1:
                    raise ValueError(f"NOP takes no operands")
                word = encode_l_type(opcode, 0, 0)

            else:
                raise ValueError(f"Unhandled instruction '{mnemonic}'")

        except ValueError as e:
            raise ValueError(f"Line {lineno}: {e}") from None

        machine_code.append(word)

    return machine_code


def write_hex(code, out, depth=256):
    padded = code + [encode_l_type(OPCODES["NOP"], 0, 0)] * (depth - len(code))
    for word in padded:
        out.write(f"{word:04X}\n")


def main():
    parser = argparse.ArgumentParser(description="Tiny CPU assembler")
    parser.add_argument("input", help="Assembly source file (.asm)")
    parser.add_argument("-o", "--output", default=None, help="Output hex file (default: stdout)")
    parser.add_argument("-d", "--depth", type=int, default=256, help="ROM depth (default: 256)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print listing")
    args = parser.parse_args()

    with open(args.input) as f:
        source = f.read()

    try:
        code = assemble(source)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        lines = source.splitlines()
        src_lines = []
        addr = 0
        for line in lines:
            stripped = line.split(";")[0].strip()
            if not stripped or stripped.endswith(":"):
                print(f"       {line}")
                continue
            print(f"  {addr:3d}  {code[addr]:04X}  {line}")
            addr += 1
        print(f"\n{len(code)} instructions assembled.")

    if args.output:
        with open(args.output, "w") as f:
            write_hex(code, f, args.depth)
    else:
        write_hex(code, sys.stdout, args.depth)


if __name__ == "__main__":
    main()
