import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotb_helpers import start_clock, reset_sync


async def reset(dut):
  dut.rx_byte.value = 0
  dut.latch_hi.value = 0
  dut.latch_lo.value = 0
  await reset_sync(dut)


@cocotb.test()
async def test_read_data_accum_reset(dut):
  """Output should be 0x0000 after reset."""
  start_clock(dut)
  dut.rst_n.value = 0
  dut.rx_byte.value = 0xFF
  dut.latch_hi.value = 1
  dut.latch_lo.value = 1
  await Timer(10, unit="ns")
  assert int(dut.read_data.value) == 0x0000, (
    f"Expected 0x0000 after reset, got {int(dut.read_data.value):#06x}"
  )


@cocotb.test()
async def test_read_data_accum_latch_hi(dut):
  """Latching hi byte only should update upper byte."""
  start_clock(dut)
  await reset(dut)

  dut.rx_byte.value = 0xAB
  dut.latch_hi.value = 1
  dut.latch_lo.value = 0
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert int(dut.read_data.value) == 0xAB00, (
    f"Expected 0xAB00, got {int(dut.read_data.value):#06x}"
  )


@cocotb.test()
async def test_read_data_accum_latch_lo(dut):
  """Latching lo byte only should update lower byte."""
  start_clock(dut)
  await reset(dut)

  dut.rx_byte.value = 0xCD
  dut.latch_hi.value = 0
  dut.latch_lo.value = 1
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert int(dut.read_data.value) == 0x00CD, (
    f"Expected 0x00CD, got {int(dut.read_data.value):#06x}"
  )


@cocotb.test()
async def test_read_data_accum_fetch_sequence(dut):
  """Simulate FETCH: latch hi byte, then lo byte."""
  start_clock(dut)
  await reset(dut)

  # Latch hi = 0xDE
  dut.rx_byte.value = 0xDE
  dut.latch_hi.value = 1
  dut.latch_lo.value = 0
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  dut.latch_hi.value = 0

  # Latch lo = 0xAD
  dut.rx_byte.value = 0xAD
  dut.latch_lo.value = 1
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")

  assert int(dut.read_data.value) == 0xDEAD, (
    f"Expected 0xDEAD, got {int(dut.read_data.value):#06x}"
  )


@cocotb.test()
async def test_read_data_accum_hold(dut):
  """Both bytes should hold when neither latch is active."""
  start_clock(dut)
  await reset(dut)

  # Load both bytes
  dut.rx_byte.value = 0xBE
  dut.latch_hi.value = 1
  dut.latch_lo.value = 1
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")

  # Deassert latches, change rx_byte
  dut.latch_hi.value = 0
  dut.latch_lo.value = 0
  dut.rx_byte.value = 0xFF
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")

  assert int(dut.read_data.value) == 0xBEBE, (
    f"Expected 0xBEBE (held), got {int(dut.read_data.value):#06x}"
  )


@cocotb.test()
async def test_read_data_accum_load_only_lo(dut):
  """Simulate LOAD: only lo byte changes, hi preserved."""
  start_clock(dut)
  await reset(dut)

  # First set both bytes
  dut.rx_byte.value = 0x12
  dut.latch_hi.value = 1
  dut.latch_lo.value = 1
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")

  # Now update only lo
  dut.rx_byte.value = 0x99
  dut.latch_hi.value = 0
  dut.latch_lo.value = 1
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")

  assert int(dut.read_data.value) == 0x1299, (
    f"Expected 0x1299, got {int(dut.read_data.value):#06x}"
  )
