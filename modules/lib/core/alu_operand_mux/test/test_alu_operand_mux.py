import cocotb
from cocotb.triggers import Timer


def sign_extend_6to8(val):
  """Sign-extend a 6-bit value to 8 bits."""
  if val & 0x20:  # bit 5 set = negative
    return val | 0xC0
  return val & 0x3F


@cocotb.test()
async def test_alu_operand_mux_sel_rs2(dut):
  """sel=0 should select rs2_data."""
  dut.rs2_data.value = 0xAB
  dut.imm6.value = 0x15
  dut.sel.value = 0
  await Timer(1, unit="ns")
  assert int(dut.alu_b.value) == 0xAB, (
    f"Expected rs2=0xAB, got {int(dut.alu_b.value):#04x}"
  )


@cocotb.test()
async def test_alu_operand_mux_sel_imm6_positive(dut):
  """sel=1 with positive imm6 (bit5=0) should zero-extend."""
  dut.rs2_data.value = 0xFF
  dut.imm6.value = 0x1F  # 011111 -> 0x1F
  dut.sel.value = 1
  await Timer(1, unit="ns")
  expected = sign_extend_6to8(0x1F)
  assert int(dut.alu_b.value) == expected, (
    f"Expected {expected:#04x}, got {int(dut.alu_b.value):#04x}"
  )


@cocotb.test()
async def test_alu_operand_mux_sel_imm6_negative(dut):
  """sel=1 with negative imm6 (bit5=1) should sign-extend."""
  dut.rs2_data.value = 0x00
  dut.imm6.value = 0x3F  # 111111 = -1 -> 0xFF
  dut.sel.value = 1
  await Timer(1, unit="ns")
  expected = sign_extend_6to8(0x3F)
  assert expected == 0xFF
  assert int(dut.alu_b.value) == expected, (
    f"Expected {expected:#04x}, got {int(dut.alu_b.value):#04x}"
  )


@cocotb.test()
async def test_alu_operand_mux_sel_imm6_minus_one(dut):
  """imm6 = 0x20 (100000 = -32) -> sign-extend to 0xE0."""
  dut.rs2_data.value = 0x00
  dut.imm6.value = 0x20
  dut.sel.value = 1
  await Timer(1, unit="ns")
  expected = sign_extend_6to8(0x20)
  assert expected == 0xE0
  assert int(dut.alu_b.value) == expected, (
    f"Expected {expected:#04x}, got {int(dut.alu_b.value):#04x}"
  )


@cocotb.test()
async def test_alu_operand_mux_exhaustive_imm6(dut):
  """Exhaustive test of all 64 imm6 values with sel=1."""
  dut.rs2_data.value = 0x00
  dut.sel.value = 1

  for imm in range(64):
    dut.imm6.value = imm
    await Timer(1, unit="ns")
    expected = sign_extend_6to8(imm)
    observed = int(dut.alu_b.value)
    assert observed == expected, (
      f"imm6={imm:#04x}: expected {expected:#04x}, got {observed:#04x}"
    )
