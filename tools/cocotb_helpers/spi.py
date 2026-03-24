"""SPI bus helpers for master-side stimulus."""

from cocotb.triggers import RisingEdge, FallingEdge, Timer
from cocotb_helpers.timing import tick


# SPI command constants
CMD_IFETCH = 0x03
CMD_LOAD   = 0x0B
CMD_STORE  = 0x02
CMD_WREN   = 0x06


async def spi_send_8(dut, value, half_period_ns=50):
  """Master sends 8 bits to slave over MOSI (MSB-first).
  Uses Timer-based SCLK — suitable for spi_phy-level tests.
  CS must already be low."""
  for i in range(7, -1, -1):
    dut.mosi.value = (value >> i) & 1
    dut.sclk.value = 0
    await Timer(half_period_ns, unit="ns")
    dut.sclk.value = 1
    await Timer(half_period_ns, unit="ns")
  dut.sclk.value = 0


async def spi_recv_8(dut, half_period_ns=50):
  """Master clocks 8 bits out of slave over MISO (MSB-first).
  Uses Timer-based SCLK — suitable for spi_phy-level tests.
  CS must already be low."""
  received = 0
  for _ in range(8):
    dut.sclk.value = 0
    await Timer(half_period_ns, unit="ns")
    dut.sclk.value = 1
    await Timer(half_period_ns, unit="ns")
    received = (received << 1) | int(dut.miso.value)
  dut.sclk.value = 0
  return received


async def spi_clock_byte(dut, tx_byte=0x00, sclk_div=5):
  """Clock one SPI byte using system-clock-derived SCLK.
  Master drives MISO with *tx_byte* (MSB-first) and samples MOSI.
  Used by integration-level tests (half_cpu, mem_ctrl).
  Does NOT include inter-byte gap — caller handles timing."""
  received = 0
  for i in range(7, -1, -1):
    dut.miso.value = (tx_byte >> i) & 1
    dut.sclk.value = 0
    await tick(dut, sclk_div)
    dut.sclk.value = 1
    await tick(dut, sclk_div)
    received = (received << 1) | int(dut.mosi.value)
  dut.sclk.value = 0
  return received
