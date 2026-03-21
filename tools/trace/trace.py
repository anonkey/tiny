#!/usr/bin/env python3
"""CPU execution trace viewer from FST waveform files.

Usage:
    python trace.py [fst_file]             # default: test/tb_cpu.fst
    python trace.py test/tb_cpu.fst -n 20  # show 20 cycles
    python trace.py test/tb_cpu.fst -r     # show register file state

Reads the FST file produced by cocotb/Icarus simulation and prints
a human-readable execution trace showing PC, instruction, decoded
mnemonic, ALU output, and optionally register file contents.
"""

import argparse
import os
import sys

import pylibfst
from pylibfst import lib

MNEMONICS = {
    0b0000: "ADD",  0b0001: "SUB",  0b0010: "AND",  0b0011: "OR",
    0b0100: "XOR",  0b0101: "NOT",  0b0110: "NAND", 0b0111: "NOR",
    0b1000: "XNOR", 0b1001: "ADDI", 0b1010: "LDI",  0b1011: "JMP",
    0b1100: "BEQ",  0b1101: "LOAD", 0b1110: "STORE", 0b1111: "NOP",
}

R_TYPE = {0,1,2,3,4,6,7,8}
U_TYPE = {5}
I_TYPE = {9,13,14}
L_TYPE = {10,11,12}


def decode_instr(word):
    """Decode 16-bit instruction into human-readable string."""
    opcode = (word >> 12) & 0xF
    rd     = (word >> 9) & 0x7
    rs1    = (word >> 6) & 0x7
    rs2    = (word >> 3) & 0x7
    imm6   = word & 0x3F
    imm8   = (word >> 1) & 0xFF
    mnem   = MNEMONICS.get(opcode, "???")

    if opcode in R_TYPE:
        return f"{mnem:4s} r{rd}, r{rs1}, r{rs2}"
    elif opcode in U_TYPE:
        return f"{mnem:4s} r{rd}, r{rs1}"
    elif opcode in I_TYPE:
        if imm6 & 0x20:
            imm6_s = imm6 - 64
        else:
            imm6_s = imm6
        return f"{mnem:4s} r{rd}, r{rs1}, {imm6_s}"
    elif opcode in L_TYPE:
        if opcode in (0b1011, 0b1100):
            return f"{mnem:4s} {imm8}"
        return f"{mnem:4s} r{rd}, {imm8}"
    else:
        return mnem


def parse_bin(s):
    """Parse a binary string like '01010011' to int. Handle 'x'/'z' as 0."""
    s = s.replace("x", "0").replace("X", "0").replace("z", "0").replace("Z", "0")
    if not s:
        return 0
    return int(s, 2)


def load_fst(path):
    """Load FST file and return signal changes as {name: [(time, value)]}."""
    ctx = lib.fstReaderOpen(path.encode())
    if ctx == pylibfst.ffi.NULL:
        print(f"Error: cannot open {path}", file=sys.stderr)
        sys.exit(1)

    _, signals = pylibfst.get_scopes_signals(ctx)

    # Build handle → name mapping (pick shortest name per handle)
    handle_to_name = {}
    for name, handle in signals.items():
        if handle not in handle_to_name or len(name) < len(handle_to_name[handle]):
            handle_to_name[handle] = name

    # Select all signals for iteration
    lib.fstReaderSetFacProcessMaskAll(ctx)

    # Collect changes — callback signature: (user_data, time, handle, value)
    changes = {}
    def callback(user_data, time, handle, value):
        name = handle_to_name.get(handle)
        if name:
            if name not in changes:
                changes[name] = []
            changes[name].append((time, pylibfst.ffi.string(value).decode()))

    pylibfst.fstReaderIterBlocks(ctx, callback)
    lib.fstReaderClose(ctx)
    return changes


def signal_at_time(changes, name, t):
    """Get the value of a signal at time t."""
    if name not in changes:
        return 0
    val = 0
    for ct, cv in changes[name]:
        if ct > t:
            break
        val = parse_bin(cv)
    return val


def find_reg_signals(changes):
    """Find register file Q output signals."""
    regs = {}
    for name in changes:
        # Pattern: tb_cpu.dut.rf.r[N].reg_i.b[M].ff.Q
        # We want the full register value, so we'll reconstruct from individual bits
        import re
        m = re.match(r'tb_cpu\.dut\.rf\.r\[(\d+)\]\.reg_i\.b\[(\d+)\]\.ff\.Q$', name)
        if m:
            reg_idx = int(m.group(1))
            bit_idx = int(m.group(2))
            if reg_idx not in regs:
                regs[reg_idx] = {}
            regs[reg_idx][bit_idx] = name
    return regs


def get_reg_values(changes, reg_signals, t):
    """Get all register values at time t."""
    values = {}
    for reg_idx, bits in sorted(reg_signals.items()):
        val = 0
        for bit_idx, name in sorted(bits.items()):
            bit_val = signal_at_time(changes, name, t)
            val |= (bit_val & 1) << bit_idx
        values[reg_idx] = val
    return values


def main():
    parser = argparse.ArgumentParser(description="CPU execution trace viewer")
    parser.add_argument("fst", nargs="?", default=None, help="FST file (default: test/tb_cpu.fst)")
    parser.add_argument("-n", "--cycles", type=int, default=0, help="Max cycles to show (0=all)")
    parser.add_argument("-r", "--regs", action="store_true", help="Show register file state")
    parser.add_argument("--last", action="store_true", help="Show only the last test run (last reset)")
    parser.add_argument("--skip-reset", action="store_true", help="Skip cycles during reset (rst_n=0)")
    args = parser.parse_args()

    # Find FST file
    if args.fst:
        fst_path = args.fst
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fst_path = os.path.join(base, "test", "tb_cpu.fst")

    if not os.path.exists(fst_path):
        print(f"Error: {fst_path} not found. Run CPU tests first.", file=sys.stderr)
        sys.exit(1)

    changes = load_fst(fst_path)

    # Find clock edges (falling edges = stable state)
    clk_name = "tb_cpu.clk"
    if clk_name not in changes:
        # Try alternative
        for name in changes:
            if name.endswith(".clk") and name.count(".") == 1:
                clk_name = name
                break

    falling_edges = []
    rising_edges = []
    prev_val = 0
    for t, v in changes.get(clk_name, []):
        cur_val = parse_bin(v)
        if prev_val == 1 and cur_val == 0:
            falling_edges.append(t)
        elif prev_val == 0 and cur_val == 1:
            rising_edges.append(t)
        prev_val = cur_val

    if not falling_edges:
        print("No clock edges found in trace.", file=sys.stderr)
        sys.exit(1)

    # Filter: --last shows only cycles after the last reset
    rst_name = "tb_cpu.rst_n"
    if args.last or args.skip_reset:
        # Find the last time rst_n goes high (end of last reset)
        last_reset_end = 0
        for t, v in changes.get(rst_name, []):
            if parse_bin(v) == 1:
                last_reset_end = t
        if args.last:
            falling_edges = [t for t in falling_edges if t >= last_reset_end]
        elif args.skip_reset:
            falling_edges = [t for t in falling_edges
                             if signal_at_time(changes, rst_name, t) == 1]

    # Signal names
    pc_name = "tb_cpu.pc_out [7:0]"
    instr_name = "tb_cpu.instr_out [15:0]"
    alu_name = "tb_cpu.alu_out [7:0]"

    # Find register bit signals
    reg_signals = find_reg_signals(changes)

    # Build header (printed per-test, not here)
    header = f"{'Cycle':>5}  {'Time':>6}  {'PC':>3}  {'Instr':>6}  {'Decoded':<22}  {'ALU':>5}"
    if reg_signals:
        header += "  " + "  ".join(f"{'r'+str(i):>3s}" for i in range(8))

    # Find reset boundaries (times where rst_n goes low)
    reset_times = []
    for t, v in changes.get(rst_name, []):
        if parse_bin(v) == 0:
            reset_times.append(t)
    reset_times.sort()

    def print_final_state(last_t, t_origin, next_reset_t=None):
        """Print register state after the last instruction's writeback."""
        if not reg_signals:
            return
        # Find the next falling edge after last_t but before the next reset
        t_final = None
        for fe in falling_edges:
            if fe > last_t:
                if next_reset_t is None or fe < next_reset_t:
                    t_final = fe
                break
        if t_final is None:
            # Writeback happens on the rising edge at the same time as reset.
            # FST records the writeback before the reset clears, so sample there.
            if next_reset_t is not None:
                t_final = next_reset_t
            elif len(falling_edges) >= 2:
                t_final = last_t + (falling_edges[-1] - falling_edges[-2])
            else:
                return
        rv = get_reg_values(changes, reg_signals, t_final)
        t_rel = (t_final - t_origin) // 1000
        regs_str = "  ".join(f"{rv.get(i,0):3d}" for i in range(8))
        print(f"{'':>5}  {t_rel:6d}ns  {'':>3}  {'':>6}  {'--- final state ---':<22s}  {'':>5}  {regs_str}")

    # Print each cycle
    limit = args.cycles if args.cycles > 0 else len(falling_edges)
    test_num = 0
    t_origin = 0
    next_reset_idx = 0
    prev_t = None
    header_printed = False
    for cycle, t in enumerate(falling_edges[:limit]):
        # Check if we crossed a reset boundary
        while next_reset_idx < len(reset_times) and reset_times[next_reset_idx] <= t:
            # Print final state of previous test before the separator
            if prev_t is not None:
                print_final_state(prev_t, t_origin, reset_times[next_reset_idx])
            next_reset_idx += 1
            test_num += 1
            t_origin = reset_times[next_reset_idx - 1]
            print(f"\n{'=' * len(header)}")
            print(f"  Test {test_num}")
            print(header)
            print("-" * len(header))
            header_printed = True

        if not header_printed:
            print(header)
            print("-" * len(header))
            header_printed = True

        pc = signal_at_time(changes, pc_name, t)
        instr = signal_at_time(changes, instr_name, t)
        alu = signal_at_time(changes, alu_name, t)
        decoded = decode_instr(instr)

        t_rel = (t - t_origin) // 1000
        line = f"{cycle:5d}  {t_rel:6d}ns  {pc:3d}  0x{instr:04X}  {decoded:<22s}  0x{alu:02X}"

        if reg_signals:
            rv = get_reg_values(changes, reg_signals, t)
            line += "  " + "  ".join(f"{rv.get(i,0):3d}" for i in range(8))

        print(line)
        prev_t = t

    # Final state of the last test
    if prev_t is not None:
        print_final_state(prev_t, t_origin)

    print(f"\n{min(limit, len(falling_edges))} cycles shown.")


if __name__ == "__main__":
    main()
