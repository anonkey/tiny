import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_pc_inc_exhaustive(dut):
  """Exhaustive test: pc_next == (pc + 1) % 256 for all 8-bit values."""
  for val in range(256):
    dut.pc.value = val
    await Timer(1, unit="ns")
    expected = (val + 1) & 0xFF
    observed = int(dut.pc_next.value)
    assert observed == expected, (
      f"pc={val:#04x}: expected {expected:#04x}, got {observed:#04x}"
    )
