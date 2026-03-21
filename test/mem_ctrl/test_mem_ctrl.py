import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge


# Memory operations
MEM_OP_FETCH = 0b00
MEM_OP_LOAD  = 0b01
MEM_OP_STORE = 0b10

# Expected SPI commands
CMD_IFETCH = 0x03
CMD_LOAD   = 0x0B
CMD_STORE  = 0x02
CMD_WREN   = 0x06


async def reset(dut):
    dut.rst_n.value = 0
    dut.spi_rx_done.value = 0
    dut.mem_req.value = 0
    dut.mem_op.value = 0
    dut.mem_addr.value = 0
    dut.mem_wdata.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1


async def tick(dut):
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)


async def pulse_mem_req(dut, op, addr, wdata=0):
    """Assert mem_req for one cycle with the given parameters."""
    dut.mem_req.value = 1
    dut.mem_op.value = op
    dut.mem_addr.value = addr
    dut.mem_wdata.value = wdata
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.mem_req.value = 0


async def wait_for_tx_load(dut, timeout=50):
    """Wait until spi_tx_load pulses high. Returns spi_tx_data value."""
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.spi_tx_load.value) == 1:
            tx = int(dut.spi_tx_data.value)
            await FallingEdge(dut.clk)
            return tx
    raise TimeoutError("spi_tx_load never went high")


async def pulse_rx_done(dut, delay=2):
    """Simulate SPI master sending rx_done after a delay."""
    for _ in range(delay):
        await tick(dut)
    dut.spi_rx_done.value = 1
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.spi_rx_done.value = 0


async def wait_for_mem_done(dut, timeout=50):
    """Wait until mem_done pulses high."""
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.mem_done.value) == 1:
            await FallingEdge(dut.clk)
            return
    raise TimeoutError("mem_done never went high")


@cocotb.test()
async def test_fetch(dut):
    """FETCH: send READ command, wait for rx_done, assert mem_done."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # Issue FETCH request
    await pulse_mem_req(dut, MEM_OP_FETCH, addr=0x42)

    # Expect SPI TX with CMD_IFETCH and address
    tx = await wait_for_tx_load(dut)
    cmd = (tx >> 8) & 0xFF
    addr = tx & 0xFF
    assert cmd == CMD_IFETCH, f"expected IFETCH 0x03, got {cmd:#04x}"
    assert addr == 0x42, f"expected addr 0x42, got {addr:#04x}"

    # Simulate master responding
    await pulse_rx_done(dut)

    # mem_done should pulse
    await wait_for_mem_done(dut)


@cocotb.test()
async def test_load(dut):
    """LOAD: send FAST_READ command, wait for rx_done, assert mem_done."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    await pulse_mem_req(dut, MEM_OP_LOAD, addr=0xAB)

    tx = await wait_for_tx_load(dut)
    cmd = (tx >> 8) & 0xFF
    addr = tx & 0xFF
    assert cmd == CMD_LOAD, f"expected LOAD 0x0B, got {cmd:#04x}"
    assert addr == 0xAB, f"expected addr 0xAB, got {addr:#04x}"

    await pulse_rx_done(dut)
    await wait_for_mem_done(dut)


@cocotb.test()
async def test_store(dut):
    """STORE: WREN + CMD + DATA sequence, assert mem_done after."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    await pulse_mem_req(dut, MEM_OP_STORE, addr=0x30, wdata=0x55)

    # Phase 1: WREN
    tx = await wait_for_tx_load(dut)
    cmd = (tx >> 8) & 0xFF
    assert cmd == CMD_WREN, f"expected WREN 0x06, got {cmd:#04x}"

    # Phase 2: STORE command with address
    tx = await wait_for_tx_load(dut)
    cmd = (tx >> 8) & 0xFF
    addr = tx & 0xFF
    assert cmd == CMD_STORE, f"expected STORE 0x02, got {cmd:#04x}"
    assert addr == 0x30, f"expected addr 0x30, got {addr:#04x}"

    # Phase 3: Data
    tx = await wait_for_tx_load(dut)
    data = tx & 0xFF
    pad = (tx >> 8) & 0xFF
    assert pad == 0x00, f"expected pad 0x00, got {pad:#04x}"
    assert data == 0x55, f"expected data 0x55, got {data:#04x}"

    # mem_done should pulse (no rx_done needed for STORE)
    await wait_for_mem_done(dut)


@cocotb.test()
async def test_back_to_back(dut):
    """Back-to-back FETCH then LOAD operations."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # First: FETCH at 0x00
    await pulse_mem_req(dut, MEM_OP_FETCH, addr=0x00)
    tx = await wait_for_tx_load(dut)
    assert (tx >> 8) & 0xFF == CMD_IFETCH
    assert (tx & 0xFF) == 0x00
    await pulse_rx_done(dut)
    await wait_for_mem_done(dut)

    # Second: LOAD at 0xFF
    await pulse_mem_req(dut, MEM_OP_LOAD, addr=0xFF)
    tx = await wait_for_tx_load(dut)
    assert (tx >> 8) & 0xFF == CMD_LOAD
    assert (tx & 0xFF) == 0xFF
    await pulse_rx_done(dut)
    await wait_for_mem_done(dut)


@cocotb.test()
async def test_idle_no_done(dut):
    """No mem_done pulse when idle (no spurious signals)."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # Wait several cycles, check mem_done stays low
    for _ in range(10):
        await RisingEdge(dut.clk)
        assert int(dut.mem_done.value) == 0, "mem_done should be 0 in idle"
        assert int(dut.spi_tx_load.value) == 0, "spi_tx_load should be 0 in idle"
