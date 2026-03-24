"""Clock initialization and reset helpers."""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer


def start_clock(dut, period_ns=10):
  """Start the system clock. Returns the forked coroutine."""
  return cocotb.start_soon(Clock(dut.clk, period_ns, unit="ns").start())


async def reset_sync(dut, clk_cycles=3):
  """Synchronous reset: hold rst_n low for *clk_cycles* rising edges,
  then release on the next falling edge.  Clock must already be running."""
  dut.rst_n.value = 0
  for _ in range(clk_cycles):
    await RisingEdge(dut.clk)
  await FallingEdge(dut.clk)
  dut.rst_n.value = 1


async def reset_async(dut, hold_ns=10):
  """Asynchronous reset: hold rst_n low for a fixed time, then release.
  Does not require the clock to be running (useful for dff/register)."""
  dut.rst_n.value = 0
  await Timer(hold_ns, unit="ns")
  dut.rst_n.value = 1
  await Timer(2, unit="ns")
