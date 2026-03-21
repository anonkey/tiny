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
    dut.spi_byte_done.value = 0
    dut.spi_rx_data.value = 0
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
    """Wait until spi_tx_load pulses high. Returns spi_tx_data (8-bit)."""
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.spi_tx_load.value) == 1:
            tx = int(dut.spi_tx_data.value)
            await FallingEdge(dut.clk)
            return tx
    raise TimeoutError("spi_tx_load never went high")


async def pulse_byte_done(dut, rx_data=0x00, delay=2):
    """Simulate SPI byte completion. Optionally provide RX data."""
    for _ in range(delay):
        await tick(dut)
    dut.spi_rx_data.value = rx_data
    dut.spi_byte_done.value = 1
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.spi_byte_done.value = 0


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
    """FETCH (READ 0x03): CMD + ADDR + 2 RX bytes, verify read_data."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # CS should be high initially
    assert int(dut.cs_n.value) == 1, "CS should be high in idle"

    await pulse_mem_req(dut, MEM_OP_FETCH, addr=0x42)

    # Byte 1: CMD (0x03)
    tx = await wait_for_tx_load(dut)
    assert tx == CMD_IFETCH, f"expected CMD 0x03, got {tx:#04x}"
    # CS should now be low
    assert int(dut.cs_n.value) == 0, "CS should be low during transaction"
    await pulse_byte_done(dut)

    # Byte 2: ADDR (0x42)
    tx = await wait_for_tx_load(dut)
    assert tx == 0x42, f"expected addr 0x42, got {tx:#04x}"
    await pulse_byte_done(dut)

    # Byte 3: RX1 — dummy TX, receive hi byte
    tx = await wait_for_tx_load(dut)
    assert tx == 0x00, f"expected dummy 0x00, got {tx:#04x}"
    await pulse_byte_done(dut, rx_data=0xBE)  # instruction hi

    # Byte 4: RX2 — dummy TX, receive lo byte
    tx = await wait_for_tx_load(dut)
    assert tx == 0x00, f"expected dummy 0x00, got {tx:#04x}"
    await pulse_byte_done(dut, rx_data=0xEF)  # instruction lo

    await wait_for_mem_done(dut)

    # Verify accumulated read data
    rd = int(dut.read_data.value)
    assert rd == 0xBEEF, f"expected read_data 0xBEEF, got {rd:#06x}"

    # CS should be high again
    assert int(dut.cs_n.value) == 1, "CS should be high after transaction"


@cocotb.test()
async def test_load(dut):
    """LOAD (FAST_READ 0x0B): CMD + ADDR + DUMMY + 1 RX byte."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    await pulse_mem_req(dut, MEM_OP_LOAD, addr=0xAB)

    # Byte 1: CMD (0x0B)
    tx = await wait_for_tx_load(dut)
    assert tx == CMD_LOAD, f"expected CMD 0x0B, got {tx:#04x}"
    assert int(dut.cs_n.value) == 0
    await pulse_byte_done(dut)

    # Byte 2: ADDR
    tx = await wait_for_tx_load(dut)
    assert tx == 0xAB, f"expected addr 0xAB, got {tx:#04x}"
    await pulse_byte_done(dut)

    # Byte 3: DUMMY
    tx = await wait_for_tx_load(dut)
    assert tx == 0x00, f"expected dummy 0x00, got {tx:#04x}"
    await pulse_byte_done(dut)

    # Byte 4: RX — receive data byte
    tx = await wait_for_tx_load(dut)
    assert tx == 0x00, f"expected dummy 0x00, got {tx:#04x}"
    await pulse_byte_done(dut, rx_data=0x55)

    await wait_for_mem_done(dut)

    # Verify read data (low byte)
    rd = int(dut.read_data.value) & 0xFF
    assert rd == 0x55, f"expected read_data[7:0] 0x55, got {rd:#04x}"

    assert int(dut.cs_n.value) == 1


@cocotb.test()
async def test_store(dut):
    """STORE: WREN (CS cycle) + WRITE CMD + ADDR + DATA (CS cycle)."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    await pulse_mem_req(dut, MEM_OP_STORE, addr=0x30, wdata=0x55)

    # --- WREN CS cycle ---
    # Byte 1: WREN (0x06)
    tx = await wait_for_tx_load(dut)
    assert tx == CMD_WREN, f"expected WREN 0x06, got {tx:#04x}"
    assert int(dut.cs_n.value) == 0, "CS should be low for WREN"
    await pulse_byte_done(dut)

    # CS should go high briefly (WREN_CS_HI state)
    await tick(dut)
    assert int(dut.cs_n.value) == 1, "CS should be high between WREN and WRITE"

    # --- WRITE CS cycle ---
    # Byte 2: WRITE CMD (0x02)
    tx = await wait_for_tx_load(dut)
    assert tx == CMD_STORE, f"expected WRITE 0x02, got {tx:#04x}"
    assert int(dut.cs_n.value) == 0, "CS should be low for WRITE"
    await pulse_byte_done(dut)

    # Byte 3: ADDR
    tx = await wait_for_tx_load(dut)
    assert tx == 0x30, f"expected addr 0x30, got {tx:#04x}"
    await pulse_byte_done(dut)

    # Byte 4: DATA
    tx = await wait_for_tx_load(dut)
    assert tx == 0x55, f"expected data 0x55, got {tx:#04x}"
    await pulse_byte_done(dut)

    await wait_for_mem_done(dut)
    assert int(dut.cs_n.value) == 1, "CS should be high after STORE"


@cocotb.test()
async def test_back_to_back(dut):
    """Back-to-back FETCH then LOAD operations."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # --- FETCH at 0x00 ---
    await pulse_mem_req(dut, MEM_OP_FETCH, addr=0x00)

    tx = await wait_for_tx_load(dut)
    assert tx == CMD_IFETCH
    await pulse_byte_done(dut)

    tx = await wait_for_tx_load(dut)
    assert tx == 0x00
    await pulse_byte_done(dut)

    # RX1 (hi)
    await wait_for_tx_load(dut)
    await pulse_byte_done(dut, rx_data=0x12)
    # RX2 (lo)
    await wait_for_tx_load(dut)
    await pulse_byte_done(dut, rx_data=0x34)

    await wait_for_mem_done(dut)
    assert int(dut.read_data.value) == 0x1234

    # --- LOAD at 0xFF ---
    await pulse_mem_req(dut, MEM_OP_LOAD, addr=0xFF)

    tx = await wait_for_tx_load(dut)
    assert tx == CMD_LOAD
    await pulse_byte_done(dut)

    tx = await wait_for_tx_load(dut)
    assert tx == 0xFF
    await pulse_byte_done(dut)

    # DUMMY
    await wait_for_tx_load(dut)
    await pulse_byte_done(dut)

    # RX
    await wait_for_tx_load(dut)
    await pulse_byte_done(dut, rx_data=0xAA)

    await wait_for_mem_done(dut)
    assert (int(dut.read_data.value) & 0xFF) == 0xAA


@cocotb.test()
async def test_idle_no_done(dut):
    """No mem_done pulse when idle (no spurious signals)."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    for _ in range(10):
        await RisingEdge(dut.clk)
        assert int(dut.mem_done.value) == 0, "mem_done should be 0 in idle"
        assert int(dut.spi_tx_load.value) == 0, "spi_tx_load should be 0 in idle"
        assert int(dut.cs_n.value) == 1, "cs_n should be high in idle"
