import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge


async def reset(dut):
    """Reset PC. After return, PC=0 and we're on a falling edge,
    with the next rising edge being the first real clock cycle."""
    dut.load.value = 0
    dut.load_addr.value = 0
    dut.en.value = 1
    dut.rst_n.value = 0
    # Need rising edges while reset is held to clear master-slave X states
    for _ in range(3):
        await RisingEdge(dut.clk)
    # Release reset on falling edge so next rising edge is first real capture
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1


async def tick(dut):
    """Advance one clock cycle. Values are set before calling, read after."""
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)


@cocotb.test()
async def test_pc_reset(dut):
    """After reset + first tick, PC should be 1 (0 + 1)."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    await tick(dut)
    assert int(dut.pc_out.value) == 1, (
        f"PC should be 1 after reset + first tick, got {int(dut.pc_out.value)}"
    )

    # Second tick: PC = 2
    await tick(dut)
    assert int(dut.pc_out.value) == 2, (
        f"PC should be 2 after second tick, got {int(dut.pc_out.value)}"
    )


@cocotb.test()
async def test_pc_increment(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # First tick: PC goes from 0 to 1
    for expected in range(1, 20):
        await tick(dut)
        observed = int(dut.pc_out.value)
        assert observed == expected, (
            f"PC should be {expected}, got {observed}"
        )


@cocotb.test()
async def test_pc_load(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # Increment 5 times → PC = 5
    for _ in range(5):
        await tick(dut)
    assert int(dut.pc_out.value) == 5

    # Load 0x42
    dut.load.value = 1
    dut.load_addr.value = 0x42
    await tick(dut)
    assert int(dut.pc_out.value) == 0x42, (
        f"PC should be 0x42 after load, got {int(dut.pc_out.value):#x}"
    )

    # Resume incrementing
    dut.load.value = 0
    await tick(dut)
    assert int(dut.pc_out.value) == 0x43, (
        f"PC should be 0x43, got {int(dut.pc_out.value):#x}"
    )


@cocotb.test()
async def test_pc_wrap(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # Load 0xFF
    dut.load.value = 1
    dut.load_addr.value = 0xFF
    await tick(dut)
    assert int(dut.pc_out.value) == 0xFF

    # Wrap to 0x00
    dut.load.value = 0
    await tick(dut)
    assert int(dut.pc_out.value) == 0x00, (
        f"PC should wrap to 0x00, got {int(dut.pc_out.value):#x}"
    )

    await tick(dut)
    assert int(dut.pc_out.value) == 0x01


@cocotb.test()
async def test_pc_load_zero(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    for _ in range(10):
        await tick(dut)
    assert int(dut.pc_out.value) == 10

    # Jump to 0
    dut.load.value = 1
    dut.load_addr.value = 0x00
    await tick(dut)
    assert int(dut.pc_out.value) == 0x00

    dut.load.value = 0
    await tick(dut)
    assert int(dut.pc_out.value) == 0x01


@cocotb.test()
async def test_pc_consecutive_loads(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    addrs = [0x10, 0x80, 0xFF, 0x00, 0x55]
    for addr in addrs:
        dut.load.value = 1
        dut.load_addr.value = addr
        await tick(dut)
        assert int(dut.pc_out.value) == addr, (
            f"PC should be {addr:#x}, got {int(dut.pc_out.value):#x}"
        )
