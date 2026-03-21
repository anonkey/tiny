import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
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
    await Timer(SYS_CLK_PERIOD * 5, units="ns")
    dut.rst_n.value = 1
    await Timer(SYS_CLK_PERIOD * 2, units="ns")


async def spi_send_16(dut, value):
    """Master sends 16 bits to slave over MOSI. Returns nothing."""
    dut.cs_n.value = 0
    await Timer(SPI_HALF_PERIOD, units="ns")

    for i in range(15, -1, -1):
        bit = (value >> i) & 1
        dut.mosi.value = bit
        dut.sclk.value = 0
        await Timer(SPI_HALF_PERIOD, units="ns")
        dut.sclk.value = 1
        await Timer(SPI_HALF_PERIOD, units="ns")

    dut.sclk.value = 0
    await Timer(SPI_HALF_PERIOD, units="ns")
    dut.cs_n.value = 1
    await Timer(SYS_CLK_PERIOD * 6, units="ns")


async def spi_recv_16(dut):
    """Master clocks 16 bits out of slave over MISO. Returns the received value."""
    received = 0
    dut.cs_n.value = 0
    dut.mosi.value = 0
    await Timer(SPI_HALF_PERIOD, units="ns")

    for _ in range(16):
        dut.sclk.value = 0
        await Timer(SPI_HALF_PERIOD, units="ns")
        # Sample MISO on rising edge
        dut.sclk.value = 1
        await Timer(SPI_HALF_PERIOD, units="ns")
        received = (received << 1) | int(dut.miso.value)

    dut.sclk.value = 0
    await Timer(SPI_HALF_PERIOD, units="ns")
    dut.cs_n.value = 1
    await Timer(SYS_CLK_PERIOD * 6, units="ns")
    return received


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
    """After reset, rx_data=0 and rx_done=0."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)
    assert int(dut.rx_data.value) == 0
    assert int(dut.rx_done.value) == 0


@cocotb.test()
async def test_rx_single(dut):
    """Receive a single 16-bit value over MOSI."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)
    await spi_send_16(dut, 0xA5F0)
    assert int(dut.rx_data.value) == 0xA5F0


@cocotb.test()
async def test_rx_multiple(dut):
    """Receive several values back-to-back."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)
    for val in [0xDEAD, 0xBEEF, 0x1234, 0x0000, 0xFFFF]:
        await spi_send_16(dut, val)
        assert int(dut.rx_data.value) == val, f"expected {val:#06x}, got {int(dut.rx_data.value):#06x}"


@cocotb.test()
async def test_rx_incomplete(dut):
    """Incomplete transfer (8 bits) should not update rx_data."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    await spi_send_16(dut, 0x1234)
    assert int(dut.rx_data.value) == 0x1234

    # Send only 8 bits
    dut.cs_n.value = 0
    await Timer(SPI_HALF_PERIOD, units="ns")
    for i in range(7, -1, -1):
        dut.mosi.value = (0xFF >> i) & 1
        dut.sclk.value = 0
        await Timer(SPI_HALF_PERIOD, units="ns")
        dut.sclk.value = 1
        await Timer(SPI_HALF_PERIOD, units="ns")
    dut.sclk.value = 0
    await Timer(SPI_HALF_PERIOD, units="ns")
    dut.cs_n.value = 1
    await Timer(SYS_CLK_PERIOD * 6, units="ns")

    assert int(dut.rx_data.value) == 0x1234


# ---- TX Tests ----

@cocotb.test()
async def test_tx_single(dut):
    """Load a value and clock it out over MISO."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    await tx_load_pulse(dut, 0xCAFE)
    received = await spi_recv_16(dut)
    assert received == 0xCAFE, f"expected 0xCAFE, got {received:#06x}"


@cocotb.test()
async def test_tx_multiple(dut):
    """Send several values over MISO back-to-back."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    for val in [0x0102, 0xFF00, 0x00FF, 0xABCD]:
        await tx_load_pulse(dut, val)
        received = await spi_recv_16(dut)
        assert received == val, f"expected {val:#06x}, got {received:#06x}"


# ---- Full duplex within a single CS (both shift simultaneously) ----

@cocotb.test()
async def test_simultaneous_tx_rx(dut):
    """During one CS assertion, MISO shifts out TX while MOSI shifts in RX."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    tx_val = 0x1234
    rx_val = 0x5678

    await tx_load_pulse(dut, tx_val)

    # Full-duplex transfer
    received_miso = 0
    dut.cs_n.value = 0
    await Timer(SPI_HALF_PERIOD, units="ns")

    for i in range(15, -1, -1):
        dut.mosi.value = (rx_val >> i) & 1
        dut.sclk.value = 0
        await Timer(SPI_HALF_PERIOD, units="ns")
        dut.sclk.value = 1
        await Timer(SPI_HALF_PERIOD, units="ns")
        received_miso = (received_miso << 1) | int(dut.miso.value)

    dut.sclk.value = 0
    await Timer(SPI_HALF_PERIOD, units="ns")
    dut.cs_n.value = 1
    await Timer(SYS_CLK_PERIOD * 6, units="ns")

    assert int(dut.rx_data.value) == rx_val, f"RX: expected {rx_val:#06x}, got {int(dut.rx_data.value):#06x}"
    assert received_miso == tx_val, f"TX: expected {tx_val:#06x}, got {received_miso:#06x}"


# ---- Protocol test: cmd+addr TX then data RX ----

@cocotb.test()
async def test_protocol_ifetch(dut):
    """Simulate instruction fetch: TX cmd=0x01 addr=0x42, then RX instruction."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    # Phase 1: chip sends cmd+addr
    cmd_addr = 0x0142  # cmd=0x01 (IFETCH), addr=0x42
    await tx_load_pulse(dut, cmd_addr)
    received_by_master = await spi_recv_16(dut)
    assert received_by_master == cmd_addr, f"master should see {cmd_addr:#06x}, got {received_by_master:#06x}"

    # Phase 2: master sends instruction back
    instruction = 0xBEEF
    await spi_send_16(dut, instruction)
    assert int(dut.rx_data.value) == instruction, f"expected {instruction:#06x}, got {int(dut.rx_data.value):#06x}"


@cocotb.test()
async def test_random_rx(dut):
    """Random RX values."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    random.seed(42)
    for _ in range(20):
        val = random.randint(0, 0xFFFF)
        await spi_send_16(dut, val)
        assert int(dut.rx_data.value) == val
