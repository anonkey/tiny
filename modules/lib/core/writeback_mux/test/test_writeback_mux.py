import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_writeback_mux_alu_result(dut):
  """use_imm8=0, load_data_sel=0 -> ALU result."""
  dut.alu_result.value = 0xAA
  dut.imm8.value = 0xBB
  dut.load_data.value = 0xCC
  dut.use_imm8.value = 0
  dut.load_data_sel.value = 0
  await Timer(1, unit="ns")
  assert int(dut.write_data.value) == 0xAA, (
    f"Expected 0xAA, got {int(dut.write_data.value):#04x}"
  )


@cocotb.test()
async def test_writeback_mux_imm8(dut):
  """use_imm8=1, load_data_sel=0 -> imm8."""
  dut.alu_result.value = 0xAA
  dut.imm8.value = 0xBB
  dut.load_data.value = 0xCC
  dut.use_imm8.value = 1
  dut.load_data_sel.value = 0
  await Timer(1, unit="ns")
  assert int(dut.write_data.value) == 0xBB, (
    f"Expected 0xBB, got {int(dut.write_data.value):#04x}"
  )


@cocotb.test()
async def test_writeback_mux_load_data(dut):
  """load_data_sel=1 -> load_data regardless of use_imm8."""
  dut.alu_result.value = 0xAA
  dut.imm8.value = 0xBB
  dut.load_data.value = 0xCC
  dut.use_imm8.value = 0
  dut.load_data_sel.value = 1
  await Timer(1, unit="ns")
  assert int(dut.write_data.value) == 0xCC, (
    f"Expected 0xCC, got {int(dut.write_data.value):#04x}"
  )

  # Also with use_imm8=1 -- load_data_sel should still win
  dut.use_imm8.value = 1
  await Timer(1, unit="ns")
  assert int(dut.write_data.value) == 0xCC, (
    f"Expected 0xCC with use_imm8=1, got {int(dut.write_data.value):#04x}"
  )


@cocotb.test()
async def test_writeback_mux_sweep(dut):
  """Sweep distinct values through each path."""
  test_cases = [
    # (use_imm8, load_data_sel, expected_source)
    (0, 0, "alu"),
    (1, 0, "imm8"),
    (0, 1, "load"),
    (1, 1, "load"),
  ]
  for use_imm8, load_sel, source in test_cases:
    dut.alu_result.value = 0x11
    dut.imm8.value = 0x22
    dut.load_data.value = 0x33
    dut.use_imm8.value = use_imm8
    dut.load_data_sel.value = load_sel
    await Timer(1, unit="ns")

    expected = {"alu": 0x11, "imm8": 0x22, "load": 0x33}[source]
    observed = int(dut.write_data.value)
    assert observed == expected, (
      f"use_imm8={use_imm8}, load_sel={load_sel}: "
      f"expected {expected:#04x} ({source}), got {observed:#04x}"
    )
