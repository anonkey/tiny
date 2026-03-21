import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge
import os


# Instruction builders
def r_type(opcode, rd, rs1, rs2):
    return (opcode << 12) | (rd << 9) | (rs1 << 6) | (rs2 << 3)

def i_type(opcode, rd, rs1, imm6):
    return (opcode << 12) | (rd << 9) | (rs1 << 6) | (imm6 & 0x3F)

def l_type(opcode, rd, imm8):
    return (opcode << 12) | (rd << 9) | ((imm8 & 0xFF) << 1)

# Opcodes
ADD  = 0b0000
SUB  = 0b0001
AND  = 0b0010
OR   = 0b0011
XOR  = 0b0100
NOT  = 0b0101
NAND = 0b0110
NOR  = 0b0111
XNOR = 0b1000
ADDI = 0b1001
LDI  = 0b1010
JMP  = 0b1011
BEQ  = 0b1100
NOP  = 0b1111

# Single program loaded into ROM at elaboration time.
# After reset, PC=1 (addr 0 executes during reset's first real edge).
# On falling edge, PC shows the address just executed and combinational
# outputs (alu_out, instr_out) reflect the NEXT instruction at the new PC.
#
# Timing model (single-cycle):
#   - On rising edge: PC register captures next_pc, regfile captures write_data
#   - Combinationally: ROM[PC] → decoder → regfile reads → ALU → result
#   - alu_out reflects the computation of the instruction at current PC
#   - On next rising edge: result written to rd, PC advances
#
# To observe ALU result of instruction at addr N:
#   Wait until PC=N (instruction is being decoded), read alu_out.
#   The result gets written to regfile on the NEXT rising edge.

PROGRAM = [
    # addr 0: LDI r0, 10
    l_type(LDI, 0, 10),
    # addr 1: LDI r1, 20
    l_type(LDI, 1, 20),
    # addr 2: ADD r2, r0, r1 → r2 = 30
    r_type(ADD, 2, 0, 1),
    # addr 3: LDI r3, 5
    l_type(LDI, 3, 5),
    # addr 4: SUB r4, r2, r3 → r4 = 25
    r_type(SUB, 4, 2, 3),
    # addr 5: LDI r5, 0xF0
    l_type(LDI, 5, 0xF0),
    # addr 6: LDI r6, 0x0F
    l_type(LDI, 6, 0x0F),
    # addr 7: AND r7, r5, r6 → 0x00
    r_type(AND, 7, 5, 6),
    # addr 8: OR r0, r5, r6 → 0xFF
    r_type(OR,  0, 5, 6),
    # addr 9: XOR r1, r5, r6 → 0xFF
    r_type(XOR, 1, 5, 6),
    # addr 10: LDI r2, 10
    l_type(LDI, 2, 10),
    # addr 11: ADDI r3, r2, 5 → 15
    i_type(ADDI, 3, 2, 5),
    # addr 12: JMP to 20
    l_type(JMP, 0, 20),
    # addr 13-19: skipped
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    # addr 20: LDI r0, 77
    l_type(LDI, 0, 77),
    # addr 21: BEQ to 30 (always taken, ALU slot 12 = 0)
    l_type(BEQ, 0, 30),
    # addr 22-29: skipped
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    l_type(NOP, 0, 0),
    # addr 30: LDI r1, 88
    l_type(LDI, 1, 88),
    # addr 31: NOP
    l_type(NOP, 0, 0),
]


def write_hex():
    path = os.path.join(os.path.dirname(__file__), "program.hex")
    padded = PROGRAM + [l_type(NOP, 0, 0)] * (256 - len(PROGRAM))
    with open(path, "w") as f:
        for word in padded:
            f.write(f"{word:04X}\n")


write_hex()


async def reset(dut):
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1


async def tick(dut):
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)


async def run_until_pc(dut, target):
    """Tick until PC equals target. Returns with PC=target on falling edge."""
    for _ in range(60):
        if int(dut.pc_out.value) == target:
            return
        await tick(dut)
    assert False, f"PC never reached {target}, stuck at {int(dut.pc_out.value)}"


@cocotb.test()
async def test_pc_increments(dut):
    """PC should increment each cycle."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # After reset, PC=1 on falling edge
    assert int(dut.pc_out.value) == 1
    # First tick: PC stays 1 (re-latches same value)
    await tick(dut)
    assert int(dut.pc_out.value) == 1
    # Second tick: PC advances to 2
    await tick(dut)
    assert int(dut.pc_out.value) == 2
    await tick(dut)
    assert int(dut.pc_out.value) == 3


@cocotb.test()
async def test_ldi_add(dut):
    """LDI r0=10, LDI r1=20, ADD r2=30. Check ALU when PC=2."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # PC=1 after reset. addr 0 (LDI r0,10) already executed.
    await run_until_pc(dut, 2)
    # PC=2: ADD r2, r0, r1 is being decoded. ALU computes r0+r1.
    assert int(dut.alu_out.value) == 30, (
        f"ADD: expected 30, got {int(dut.alu_out.value)}"
    )


@cocotb.test()
async def test_sub(dut):
    """SUB r4 = r2 - r3 = 25. Check ALU when PC=4."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)
    await run_until_pc(dut, 4)
    assert int(dut.alu_out.value) == 25, (
        f"SUB: expected 25, got {int(dut.alu_out.value)}"
    )


@cocotb.test()
async def test_logic_ops(dut):
    """AND, OR, XOR at addr 7-9."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    await run_until_pc(dut, 7)
    assert int(dut.alu_out.value) == 0x00, (
        f"AND: expected 0x00, got {int(dut.alu_out.value):#x}"
    )
    await tick(dut)  # PC=8: OR
    assert int(dut.alu_out.value) == 0xFF, (
        f"OR: expected 0xFF, got {int(dut.alu_out.value):#x}"
    )
    await tick(dut)  # PC=9: XOR
    assert int(dut.alu_out.value) == 0xFF, (
        f"XOR: expected 0xFF, got {int(dut.alu_out.value):#x}"
    )


@cocotb.test()
async def test_addi(dut):
    """ADDI r3 = r2 + 5 = 15. Check ALU when PC=11."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)
    await run_until_pc(dut, 11)
    assert int(dut.alu_out.value) == 15, (
        f"ADDI: expected 15, got {int(dut.alu_out.value)}"
    )


@cocotb.test()
async def test_jmp(dut):
    """JMP at addr 12 should set PC to 20."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)
    await run_until_pc(dut, 12)
    await tick(dut)  # execute JMP
    assert int(dut.pc_out.value) == 20, (
        f"PC should be 20 after JMP, got {int(dut.pc_out.value)}"
    )


@cocotb.test()
async def test_beq(dut):
    """BEQ at addr 21 should branch to 30."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)
    await run_until_pc(dut, 21)
    await tick(dut)  # execute BEQ
    assert int(dut.pc_out.value) == 30, (
        f"PC should be 30 after BEQ, got {int(dut.pc_out.value)}"
    )


@cocotb.test()
async def test_full_program(dut):
    """Run entire program, verify JMP and BEQ flow."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    await run_until_pc(dut, 12)
    await tick(dut)
    assert int(dut.pc_out.value) == 20, "JMP should land at 20"
    await tick(dut)
    assert int(dut.pc_out.value) == 21
    await tick(dut)
    assert int(dut.pc_out.value) == 30, "BEQ should land at 30"
    await tick(dut)
    assert int(dut.pc_out.value) == 31
