import cocotb
from cocotb.triggers import Timer
import random


async def apply_and_check(dut, a, b, opcode, expected_result, expected_carry):
  dut.a.value = a
  dut.b.value = b
  dut.opcode.value = opcode
  await Timer(1, unit="ns")

  obs_result = int(dut.result.value) & 0xFF
  obs_carry = int(dut.carry.value) & 0x1

  assert obs_result == expected_result, (
    f"op={opcode} a={a:#04x} b={b:#04x}: "
    f"result got={obs_result:#04x}, expected={expected_result:#04x}"
  )
  assert obs_carry == expected_carry, (
    f"op={opcode} a={a:#04x} b={b:#04x}: "
    f"carry got={obs_carry}, expected={expected_carry}"
  )


def compute_expected(a, b, opcode):
  if opcode == 0:  # ADD
    s = a + b
    return s & 0xFF, (s >> 8) & 1
  elif opcode == 1:  # SUB
    s = a + ((b ^ 0xFF) + 1)
    return s & 0xFF, (s >> 8) & 1
  elif opcode == 2:  # AND
    return (a & b) & 0xFF, 0
  elif opcode == 3:  # OR
    return (a | b) & 0xFF, 0
  elif opcode == 4:  # XOR
    return (a ^ b) & 0xFF, 0
  elif opcode == 5:  # NOT
    return (~a) & 0xFF, 0
  else:
    return 0, 0


@cocotb.test()
async def test_alu_add(dut):
  for a in range(256):
    for b in range(256):
      exp_r, exp_c = compute_expected(a, b, 0)
      await apply_and_check(dut, a, b, 0, exp_r, exp_c)


@cocotb.test()
async def test_alu_sub(dut):
  for a in range(256):
    for b in range(256):
      exp_r, exp_c = compute_expected(a, b, 1)
      await apply_and_check(dut, a, b, 1, exp_r, exp_c)


@cocotb.test()
async def test_alu_logic_exhaustive(dut):
  for opcode in range(2, 6):
    for a in range(256):
      for b in range(256):
        exp_r, exp_c = compute_expected(a, b, opcode)
        await apply_and_check(dut, a, b, opcode, exp_r, exp_c)


@cocotb.test()
async def test_alu_edge_cases(dut):
  edges = [0x00, 0x01, 0x7F, 0x80, 0xFE, 0xFF]
  for opcode in range(6):
    for a in edges:
      for b in edges:
        exp_r, exp_c = compute_expected(a, b, opcode)
        await apply_and_check(dut, a, b, opcode, exp_r, exp_c)


@cocotb.test()
async def test_alu_unused_opcodes_zero(dut):
  for opcode in range(6, 16):
    for _ in range(16):
      a = random.randint(0, 255)
      b = random.randint(0, 255)
      dut.a.value = a
      dut.b.value = b
      dut.opcode.value = opcode
      await Timer(1, unit="ns")

      obs_result = int(dut.result.value) & 0xFF
      obs_carry = int(dut.carry.value) & 0x1

      assert obs_result == 0, (
        f"Unused opcode={opcode} a={a:#04x} b={b:#04x}: "
        f"result should be 0, got={obs_result:#04x}"
      )
      assert obs_carry == 0, (
        f"Unused opcode={opcode}: carry should be 0, got={obs_carry}"
      )
