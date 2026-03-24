import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotb_helpers import start_clock, reset_async

STAGES = 2


async def reset(dut):
  dut.async_in.value = 0
  await reset_async(dut)


@cocotb.test()
async def test_reset(dut):
  """sync should be 0 after reset regardless of async_in."""
  start_clock(dut)
  dut.async_in.value = 1
  dut.rst_n.value = 0
  await Timer(10, unit="ns")

  assert dut.sync.value == 0, f"sync should be 0 after reset, got {int(dut.sync.value)}"
  assert dut.rise.value == 0, f"rise should be 0 after reset, got {int(dut.rise.value)}"
  assert dut.fall.value == 0, f"fall should be 0 after reset, got {int(dut.fall.value)}"


@cocotb.test()
async def test_propagation_high(dut):
  """async_in 0->1 should take exactly STAGES clocks to reach sync."""
  start_clock(dut)
  await reset(dut)

  dut.async_in.value = 1

  # Should NOT be through after STAGES-1 clocks
  for _ in range(STAGES - 1):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
  assert dut.sync.value == 0, f"sync should still be 0 after {STAGES - 1} clocks"

  # Should be through after one more clock
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert dut.sync.value == 1, f"sync should be 1 after {STAGES} clocks, got {int(dut.sync.value)}"


@cocotb.test()
async def test_propagation_low(dut):
  """async_in 1->0 should take exactly STAGES clocks to reach sync."""
  start_clock(dut)
  await reset(dut)

  # First propagate a 1
  dut.async_in.value = 1
  for _ in range(STAGES):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
  assert dut.sync.value == 1

  # Now drive 0
  dut.async_in.value = 0

  for _ in range(STAGES - 1):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
  assert dut.sync.value == 1, f"sync should still be 1 after {STAGES - 1} clocks"

  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert dut.sync.value == 0, f"sync should be 0 after {STAGES} clocks, got {int(dut.sync.value)}"


@cocotb.test()
async def test_stable_passthrough(dut):
  """sync should stay stable when async_in is held constant."""
  start_clock(dut)
  await reset(dut)

  dut.async_in.value = 1
  # Wait for propagation plus extra clocks
  for _ in range(STAGES + 4):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")

  # Verify stable for several more clocks
  for i in range(5):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
    assert dut.sync.value == 1, f"sync should stay 1, got {int(dut.sync.value)} at clock {i}"


@cocotb.test()
async def test_glitch_rejection(dut):
  """A sub-cycle pulse on async_in should not propagate through."""
  start_clock(dut)
  await reset(dut)

  # Wait for a rising edge then pulse async_in for less than one clock period
  await RisingEdge(dut.clk)
  await Timer(1, unit="ns")
  dut.async_in.value = 1
  await Timer(3, unit="ns")  # 3ns pulse (< 5ns half-period)
  dut.async_in.value = 0

  # Wait enough clocks for anything to propagate
  for _ in range(STAGES + 2):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")

  assert dut.sync.value == 0, f"sync should be 0 after glitch, got {int(dut.sync.value)}"


@cocotb.test()
async def test_rising_edge_pulse(dut):
  """rise should pulse for exactly 1 clock after sync goes 0->1."""
  start_clock(dut)
  await reset(dut)

  dut.async_in.value = 1

  # Wait for sync to go high
  for _ in range(STAGES):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
  assert dut.sync.value == 1

  # rise should be 1 on the same cycle sync transitions (combinational: i_sync & ~w_prev)
  assert dut.rise.value == 1, f"rise should be 1, got {int(dut.rise.value)}"
  assert dut.fall.value == 0, f"fall should be 0, got {int(dut.fall.value)}"

  # Next clock: rise should return to 0 (w_prev catches up)
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert dut.rise.value == 0, f"rise should return to 0, got {int(dut.rise.value)}"


@cocotb.test()
async def test_falling_edge_pulse(dut):
  """fall should pulse for exactly 1 clock after sync goes 1->0."""
  start_clock(dut)
  await reset(dut)

  # Propagate a 1 and let edge_detect settle
  dut.async_in.value = 1
  for _ in range(STAGES + 2):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")

  # Now drive 0
  dut.async_in.value = 0
  for _ in range(STAGES):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
  assert dut.sync.value == 0

  # fall should be 1 on the same cycle sync drops (combinational: ~i_sync & w_prev)
  assert dut.fall.value == 1, f"fall should be 1, got {int(dut.fall.value)}"
  assert dut.rise.value == 0, f"rise should be 0, got {int(dut.rise.value)}"

  # Next clock: fall should return to 0 (w_prev catches up)
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert dut.fall.value == 0, f"fall should return to 0, got {int(dut.fall.value)}"


@cocotb.test()
async def test_no_edge_when_stable(dut):
  """rise and fall should both be 0 when sync is held constant."""
  start_clock(dut)
  await reset(dut)

  # Let everything settle at 0
  for _ in range(STAGES + 2):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")

  for i in range(5):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
    assert dut.rise.value == 0, f"rise should be 0 when stable, clock {i}"
    assert dut.fall.value == 0, f"fall should be 0 when stable, clock {i}"


@cocotb.test()
async def test_full_pipeline_timing(dut):
  """End-to-end: async->sync takes STAGES clocks, edge pulse 1 clock later."""
  start_clock(dut)
  await reset(dut)

  # Let edge_detect settle
  for _ in range(STAGES + 2):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")

  # Drive async_in high
  dut.async_in.value = 1

  # After STAGES clocks: sync=1, rise not yet
  for _ in range(STAGES):
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
  assert dut.sync.value == 1, "sync should be 1 after STAGES clocks"
  # rise fires combinationally on the same cycle sync transitions
  assert dut.rise.value == 1, f"rise should be 1 when sync transitions, got {int(dut.rise.value)}"

  # After 1 more clock: rise back to 0 (w_prev catches up)
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert dut.rise.value == 0, "rise should return to 0"
