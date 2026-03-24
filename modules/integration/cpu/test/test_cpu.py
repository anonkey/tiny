import cocotb
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb_helpers import start_clock, reset_sync, tick
from cocotb_helpers.isa import (
  enc_r, enc_imm6, enc_imm8, enc_bez,
  OP_ADD, OP_SUB, OP_AND, OP_OR, OP_XOR,
  OP_ADDI, OP_LDI, OP_JMP, OP_BEZ, OP_NOP,
)
import os


# Single program loaded into ROM at elaboration time.
# After reset, PC=0. The first rising edge with rst_n=1 captures PC+1=1.
# On falling edge, PC shows the address just executed and combinational
# outputs (alu_out, instr_out) reflect the NEXT instruction at the new PC.
#
# Timing model (single-cycle):
#   - On rising edge: PC register captures next_pc, regfile captures write_data
#   - Combinationally: ROM[PC] -> decoder -> regfile reads -> ALU -> result
#   - alu_out reflects the computation of the instruction at current PC
#   - On next rising edge: result written to rd, PC advances
#
# To observe ALU result of instruction at addr N:
#   Wait until PC=N (instruction is being decoded), read alu_out.
#   The result gets written to regfile on the NEXT rising edge.

PROGRAM = [
  # NOTE: r0 is hardwired to zero — avoid using r0 for data storage.
  # addr 0: LDI r1, 10
  enc_imm8(OP_LDI, 1, 10),
  # addr 1: LDI r2, 20
  enc_imm8(OP_LDI, 2, 20),
  # addr 2: ADD r3, r1, r2 -> r3 = 30
  enc_r(OP_ADD, 3, 1, 2),
  # addr 3: LDI r4, 5
  enc_imm8(OP_LDI, 4, 5),
  # addr 4: SUB r5, r3, r4 -> r5 = 25
  enc_r(OP_SUB, 5, 3, 4),
  # addr 5: LDI r6, 0xF0
  enc_imm8(OP_LDI, 6, 0xF0),
  # addr 6: LDI r7, 0x0F
  enc_imm8(OP_LDI, 7, 0x0F),
  # addr 7: AND r1, r6, r7 -> 0x00
  enc_r(OP_AND, 1, 6, 7),
  # addr 8: OR r2, r6, r7 -> 0xFF
  enc_r(OP_OR, 2, 6, 7),
  # addr 9: XOR r3, r6, r7 -> 0xFF
  enc_r(OP_XOR, 3, 6, 7),
  # addr 10: LDI r4, 10
  enc_imm8(OP_LDI, 4, 10),
  # addr 11: ADDI r5, r4, 5 -> 15
  enc_imm6(OP_ADDI, 5, 4, 5),
  # addr 12: JMP to 20
  enc_imm8(OP_JMP, 0, 20),
  # addr 13-19: skipped
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  # addr 20: LDI r1, 77 (non-zero)
  enc_imm8(OP_LDI, 1, 77),
  # addr 21: BEZ r1, 30 -- NOT taken (r1=77 != 0), falls through to 22
  enc_bez(1, 30),
  # addr 22: LDI r1, 0 (zero)
  enc_imm8(OP_LDI, 1, 0),
  # addr 23: BEZ r1, 30 -- taken (r1=0)
  enc_bez(1, 30),
  # addr 24-29: skipped
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  enc_imm8(OP_NOP, 0, 0),
  # addr 30: LDI r2, 88
  enc_imm8(OP_LDI, 2, 88),
  # addr 31: NOP
  enc_imm8(OP_NOP, 0, 0),
]


def write_hex():
  padded = PROGRAM + [enc_imm8(OP_NOP, 0, 0)] * (256 - len(PROGRAM))
  # Write to both test dir (for reference) and cwd (where iverilog sim runs)
  for path in [os.path.join(os.path.dirname(__file__), "program.hex"), "program.hex"]:
    with open(path, "w") as f:
      for word in padded:
        f.write(f"{word:04X}\n")


write_hex()


async def reset(dut):
  await reset_sync(dut)


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
  start_clock(dut)
  await reset(dut)

  # After reset, PC=0 (rst_n released on falling edge, no posedge yet)
  assert int(dut.pc_out.value) == 0
  # First tick: posedge captures next_pc=1
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
  start_clock(dut)
  await reset(dut)

  # PC=0 after reset. run_until_pc ticks until PC reaches target.
  await run_until_pc(dut, 2)
  # PC=2: ADD r2, r0, r1 is being decoded. ALU computes r0+r1.
  assert int(dut.alu_out.value) == 30, (
    f"ADD: expected 30, got {int(dut.alu_out.value)}"
  )


@cocotb.test()
async def test_sub(dut):
  """SUB r4 = r2 - r3 = 25. Check ALU when PC=4."""
  start_clock(dut)
  await reset(dut)
  await run_until_pc(dut, 4)
  assert int(dut.alu_out.value) == 25, (
    f"SUB: expected 25, got {int(dut.alu_out.value)}"
  )


@cocotb.test()
async def test_logic_ops(dut):
  """AND, OR, XOR at addr 7-9."""
  start_clock(dut)
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
  start_clock(dut)
  await reset(dut)
  await run_until_pc(dut, 11)
  assert int(dut.alu_out.value) == 15, (
    f"ADDI: expected 15, got {int(dut.alu_out.value)}"
  )


@cocotb.test()
async def test_jmp(dut):
  """JMP at addr 12 should set PC to 20."""
  start_clock(dut)
  await reset(dut)
  await run_until_pc(dut, 12)
  await tick(dut)  # execute JMP
  assert int(dut.pc_out.value) == 20, (
    f"PC should be 20 after JMP, got {int(dut.pc_out.value)}"
  )


@cocotb.test()
async def test_bez_not_taken(dut):
  """BEZ r0, 30 at addr 21 should NOT branch (r0=77 != 0)."""
  start_clock(dut)
  await reset(dut)
  await run_until_pc(dut, 21)
  await tick(dut)  # execute BEZ r0, 30 -- r0=77, not taken
  assert int(dut.pc_out.value) == 22, (
    f"PC should be 22 (fall through), got {int(dut.pc_out.value)}"
  )


@cocotb.test()
async def test_bez_taken(dut):
  """BEZ r0, 30 at addr 23 should branch (r0=0)."""
  start_clock(dut)
  await reset(dut)
  await run_until_pc(dut, 23)
  await tick(dut)  # execute BEZ r0, 30 -- r0=0, taken
  assert int(dut.pc_out.value) == 30, (
    f"PC should be 30 after BEZ, got {int(dut.pc_out.value)}"
  )


@cocotb.test()
async def test_full_program(dut):
  """Run entire program, verify JMP and BEZ flow."""
  start_clock(dut)
  await reset(dut)

  await run_until_pc(dut, 12)
  await tick(dut)
  assert int(dut.pc_out.value) == 20, "JMP should land at 20"
  await tick(dut)
  assert int(dut.pc_out.value) == 21
  await tick(dut)  # BEZ r0, 30 -- r0=77, not taken
  assert int(dut.pc_out.value) == 22, "BEZ should fall through (r0 != 0)"
  await tick(dut)  # LDI r0, 0
  assert int(dut.pc_out.value) == 23
  await tick(dut)  # BEZ r0, 30 -- r0=0, taken
  assert int(dut.pc_out.value) == 30, "BEZ should land at 30 (r0 == 0)"
  await tick(dut)
  assert int(dut.pc_out.value) == 31
