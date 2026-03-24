"""Timing helpers: tick, wait_for."""

from cocotb.triggers import RisingEdge, FallingEdge


async def tick(dut, n=1):
  """Advance *n* full clock cycles (rising + falling edge each)."""
  for _ in range(n):
    await RisingEdge(dut.clk)
  await FallingEdge(dut.clk)


async def wait_for(dut, signal, value=1, timeout=50):
  """Poll *signal* on each rising edge until it equals *value*.
  Settles on the following falling edge.  Raises TimeoutError after
  *timeout* cycles."""
  for _ in range(timeout):
    await RisingEdge(dut.clk)
    if int(signal.value) == value:
      await FallingEdge(dut.clk)
      return
  raise TimeoutError(
    f"{signal._path} never reached {value} within {timeout} cycles"
  )
