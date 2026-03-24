import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotb_helpers import start_clock, reset_sync


async def reset(dut):
  dut.D.value = 0
  dut.latch.value = 0
  await reset_sync(dut)


@cocotb.test()
async def test_pipeline_reg_reset(dut):
  """Q should be 0 after reset."""
  start_clock(dut)
  dut.rst_n.value = 0
  dut.D.value = 0xFF
  dut.latch.value = 1
  await Timer(10, unit="ns")
  assert int(dut.Q.value) == 0, (
    f"Q should be 0x00 after reset, got {int(dut.Q.value):#04x}"
  )


@cocotb.test()
async def test_pipeline_reg_latch(dut):
  """Q should capture D when latch=1."""
  start_clock(dut)
  await reset(dut)

  dut.latch.value = 1
  dut.D.value = 0xA5
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert int(dut.Q.value) == 0xA5, (
    f"Q should be 0xA5, got {int(dut.Q.value):#04x}"
  )


@cocotb.test()
async def test_pipeline_reg_hold(dut):
  """Q should hold value when latch=0."""
  start_clock(dut)
  await reset(dut)

  # Load a value
  dut.latch.value = 1
  dut.D.value = 0x42
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert int(dut.Q.value) == 0x42

  # Disable latch, change D
  dut.latch.value = 0
  dut.D.value = 0xFF
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert int(dut.Q.value) == 0x42, (
    f"Q should hold at 0x42, got {int(dut.Q.value):#04x}"
  )


@cocotb.test()
async def test_pipeline_reg_sequential(dut):
  """Load multiple values in sequence."""
  start_clock(dut)
  await reset(dut)
  dut.latch.value = 1

  values = [0x00, 0xFF, 0xA5, 0x5A, 0x0F, 0xF0, 0x01, 0x80]
  for val in values:
    dut.D.value = val
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
    assert int(dut.Q.value) == val, (
      f"Q should be {val:#04x}, got {int(dut.Q.value):#04x}"
    )


@cocotb.test()
async def test_pipeline_reg_latch_toggle(dut):
  """Alternating latch/hold cycles."""
  start_clock(dut)
  await reset(dut)

  held = 0
  for i in range(10):
    latch_en = i % 2
    d_val = (i * 0x1B) & 0xFF
    dut.latch.value = latch_en
    dut.D.value = d_val
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
    if latch_en:
      held = d_val
    assert int(dut.Q.value) == held, (
      f"cycle {i}: latch={latch_en}, D={d_val:#04x}, "
      f"expected Q={held:#04x}, got {int(dut.Q.value):#04x}"
    )
