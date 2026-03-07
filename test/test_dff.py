import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer


async def reset(dut):
    dut.rst_n.value = 0
    dut.D.value = 0
    dut.en.value = 0
    await Timer(10, units="ns")
    dut.rst_n.value = 1
    await Timer(2, units="ns")


@cocotb.test()
async def test_dff_reset(dut):
    """Q should be 0 after async reset."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    dut.D.value = 1
    dut.en.value = 1
    await Timer(10, units="ns")

    assert dut.Q.value == 0, f"Q should be 0 after reset, got {int(dut.Q.value)}"
    assert dut.Qn.value == 1, f"Qn should be 1 after reset, got {int(dut.Qn.value)}"


@cocotb.test()
async def test_dff_load(dut):
    """Q should capture D on rising clock edge when en=1."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    dut.en.value = 1
    dut.D.value = 1
    await RisingEdge(dut.clk)
    await Timer(2, units="ns")

    assert dut.Q.value == 1, f"Q should be 1 after loading D=1, got {int(dut.Q.value)}"
    assert dut.Qn.value == 0, f"Qn should be 0, got {int(dut.Qn.value)}"


@cocotb.test()
async def test_dff_hold(dut):
    """Q should hold its value when en=0."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # Load a 1
    dut.en.value = 1
    dut.D.value = 1
    await RisingEdge(dut.clk)
    await Timer(2, units="ns")
    assert dut.Q.value == 1

    # Disable enable, change D
    dut.en.value = 0
    dut.D.value = 0
    await RisingEdge(dut.clk)
    await Timer(2, units="ns")

    assert dut.Q.value == 1, f"Q should hold at 1 when en=0, got {int(dut.Q.value)}"


@cocotb.test()
async def test_dff_toggle(dut):
    """Q should follow D transitions correctly."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)
    dut.en.value = 1

    for val in [1, 0, 1, 1, 0, 0, 1, 0]:
        dut.D.value = val
        await RisingEdge(dut.clk)
        await Timer(2, units="ns")
        assert dut.Q.value == val, f"Q should be {val}, got {int(dut.Q.value)}"
