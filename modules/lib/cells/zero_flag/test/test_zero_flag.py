import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_zero_flag_zero_input(dut):
  """Output should be 1 when all bits are zero."""
  dut.data.value = 0x00
  await Timer(1, unit="ns")
  assert int(dut.zero.value) == 1, (
    f"Expected zero=1 for data=0x00, got {int(dut.zero.value)}"
  )


@cocotb.test()
async def test_zero_flag_single_bit_set(dut):
  """Output should be 0 when any single bit is set."""
  for bit in range(8):
    dut.data.value = 1 << bit
    await Timer(1, unit="ns")
    assert int(dut.zero.value) == 0, (
      f"Expected zero=0 for data={1 << bit:#04x}, got {int(dut.zero.value)}"
    )


@cocotb.test()
async def test_zero_flag_all_ones(dut):
  """Output should be 0 when all bits are set."""
  dut.data.value = 0xFF
  await Timer(1, unit="ns")
  assert int(dut.zero.value) == 0, (
    f"Expected zero=0 for data=0xFF, got {int(dut.zero.value)}"
  )


@cocotb.test()
async def test_zero_flag_exhaustive(dut):
  """Exhaustive test: zero=1 iff data==0."""
  for val in range(256):
    dut.data.value = val
    await Timer(1, unit="ns")
    expected = 1 if val == 0 else 0
    assert int(dut.zero.value) == expected, (
      f"data={val:#04x}: expected zero={expected}, got {int(dut.zero.value)}"
    )
