import cocotb
from cocotb.triggers import RisingEdge, FallingEdge, Timer
from cocotb_helpers import start_clock, spi_send_8, spi_recv_8
import random


SYS_CLK_PERIOD = 10  # ns
SPI_HALF_PERIOD = 50  # ns


async def reset(dut):
  dut.rst_n.value = 0
  dut.sclk.value = 0
  dut.mosi.value = 0
  dut.cs_n.value = 1
  dut.tx_data.value = 0
  dut.tx_load.value = 0
  await Timer(SYS_CLK_PERIOD * 5, unit="ns")
  dut.rst_n.value = 1
  await Timer(SYS_CLK_PERIOD * 2, unit="ns")


async def tx_load_pulse(dut, value):
  """Load a value into the TX shift register."""
  await FallingEdge(dut.clk)
  dut.tx_data.value = value
  dut.tx_load.value = 1
  await RisingEdge(dut.clk)
  await FallingEdge(dut.clk)
  dut.tx_load.value = 0


# ---- RX Tests ----

@cocotb.test()
async def test_reset(dut):
  """After reset, rx_data=0 and byte_done=0."""
  start_clock(dut)
  await reset(dut)
  assert int(dut.rx_data.value) == 0
  assert int(dut.byte_done.value) == 0


@cocotb.test()
async def test_rx_single(dut):
  """Receive a single 8-bit byte over MOSI."""
  start_clock(dut)
  await reset(dut)

  dut.cs_n.value = 0
  await Timer(SPI_HALF_PERIOD, unit="ns")
  await spi_send_8(dut, 0xA5, SPI_HALF_PERIOD)
  await Timer(SPI_HALF_PERIOD, unit="ns")
  dut.cs_n.value = 1
  await Timer(SYS_CLK_PERIOD * 6, unit="ns")

  assert int(dut.rx_data.value) == 0xA5


@cocotb.test()
async def test_rx_multiple(dut):
  """Receive several bytes back-to-back within one CS assertion."""
  start_clock(dut)
  await reset(dut)

  dut.cs_n.value = 0
  await Timer(SPI_HALF_PERIOD, unit="ns")

  for val in [0xDE, 0xAD, 0xBE, 0xEF]:
    await spi_send_8(dut, val, SPI_HALF_PERIOD)
    # Wait for byte_done to propagate
    await Timer(SYS_CLK_PERIOD * 4, unit="ns")
    assert int(dut.rx_data.value) == val, \
      f"expected {val:#04x}, got {int(dut.rx_data.value):#04x}"

  dut.cs_n.value = 1
  await Timer(SYS_CLK_PERIOD * 4, unit="ns")


@cocotb.test()
async def test_rx_incomplete(dut):
  """Incomplete transfer (4 bits) should not update rx_data."""
  start_clock(dut)
  await reset(dut)

  # Send a full byte first
  dut.cs_n.value = 0
  await Timer(SPI_HALF_PERIOD, unit="ns")
  await spi_send_8(dut, 0x42, SPI_HALF_PERIOD)
  await Timer(SYS_CLK_PERIOD * 4, unit="ns")
  assert int(dut.rx_data.value) == 0x42

  # Send only 4 bits (incomplete)
  for i in range(3, -1, -1):
    dut.mosi.value = (0xF >> i) & 1
    dut.sclk.value = 0
    await Timer(SPI_HALF_PERIOD, unit="ns")
    dut.sclk.value = 1
    await Timer(SPI_HALF_PERIOD, unit="ns")
  dut.sclk.value = 0

  # Deassert CS (abort)
  dut.cs_n.value = 1
  await Timer(SYS_CLK_PERIOD * 6, unit="ns")

  # rx_data should still be 0x42
  assert int(dut.rx_data.value) == 0x42


# ---- TX Tests ----

@cocotb.test()
async def test_tx_single(dut):
  """Load a byte and clock it out over MISO."""
  start_clock(dut)
  await reset(dut)

  await tx_load_pulse(dut, 0xCA)

  dut.cs_n.value = 0
  await Timer(SPI_HALF_PERIOD, unit="ns")
  received = await spi_recv_8(dut, SPI_HALF_PERIOD)
  await Timer(SPI_HALF_PERIOD, unit="ns")
  dut.cs_n.value = 1
  await Timer(SYS_CLK_PERIOD * 6, unit="ns")

  assert received == 0xCA, f"expected 0xCA, got {received:#04x}"


@cocotb.test()
async def test_tx_multiple(dut):
  """Send several bytes over MISO, reloading between each."""
  start_clock(dut)
  await reset(dut)

  for val in [0x01, 0xFF, 0x55, 0xAB]:
    await tx_load_pulse(dut, val)
    dut.cs_n.value = 0
    await Timer(SPI_HALF_PERIOD, unit="ns")
    received = await spi_recv_8(dut, SPI_HALF_PERIOD)
    await Timer(SPI_HALF_PERIOD, unit="ns")
    dut.cs_n.value = 1
    await Timer(SYS_CLK_PERIOD * 6, unit="ns")
    assert received == val, f"expected {val:#04x}, got {received:#04x}"


# ---- Full duplex within a single CS ----

@cocotb.test()
async def test_simultaneous_tx_rx(dut):
  """During one CS assertion, MISO shifts out TX while MOSI shifts in RX."""
  start_clock(dut)
  await reset(dut)

  tx_val = 0x3C
  rx_val = 0xA5

  await tx_load_pulse(dut, tx_val)

  received_miso = 0
  dut.cs_n.value = 0
  await Timer(SPI_HALF_PERIOD, unit="ns")

  for i in range(7, -1, -1):
    dut.mosi.value = (rx_val >> i) & 1
    dut.sclk.value = 0
    await Timer(SPI_HALF_PERIOD, unit="ns")
    dut.sclk.value = 1
    await Timer(SPI_HALF_PERIOD, unit="ns")
    received_miso = (received_miso << 1) | int(dut.miso.value)

  dut.sclk.value = 0
  await Timer(SPI_HALF_PERIOD, unit="ns")
  dut.cs_n.value = 1
  await Timer(SYS_CLK_PERIOD * 6, unit="ns")

  assert int(dut.rx_data.value) == rx_val, \
    f"RX: expected {rx_val:#04x}, got {int(dut.rx_data.value):#04x}"
  assert received_miso == tx_val, \
    f"TX: expected {tx_val:#04x}, got {received_miso:#04x}"


# ---- Multi-byte back-to-back (counter resets at 8) ----

@cocotb.test()
async def test_multi_byte_continuous(dut):
  """Two bytes back-to-back within one CS: counter auto-resets at 8."""
  start_clock(dut)
  await reset(dut)

  dut.cs_n.value = 0
  await Timer(SPI_HALF_PERIOD, unit="ns")

  # Byte 1
  await spi_send_8(dut, 0x11, SPI_HALF_PERIOD)
  await Timer(SYS_CLK_PERIOD * 4, unit="ns")
  assert int(dut.rx_data.value) == 0x11

  # Byte 2 -- counter should have auto-reset
  await spi_send_8(dut, 0x22, SPI_HALF_PERIOD)
  await Timer(SYS_CLK_PERIOD * 4, unit="ns")
  assert int(dut.rx_data.value) == 0x22

  dut.cs_n.value = 1
  await Timer(SYS_CLK_PERIOD * 4, unit="ns")


# ---- Random byte test ----

@cocotb.test()
async def test_random_rx(dut):
  """Random RX byte values."""
  start_clock(dut)
  await reset(dut)

  random.seed(42)
  for _ in range(20):
    val = random.randint(0, 0xFF)
    dut.cs_n.value = 0
    await Timer(SPI_HALF_PERIOD, unit="ns")
    await spi_send_8(dut, val, SPI_HALF_PERIOD)
    await Timer(SYS_CLK_PERIOD * 4, unit="ns")
    assert int(dut.rx_data.value) == val
    dut.cs_n.value = 1
    await Timer(SYS_CLK_PERIOD * 4, unit="ns")
