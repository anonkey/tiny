import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

SYS_CLK_PERIOD = 10

@cocotb.test()
async def test_tx_debug(dut):
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())

    # Reset
    dut.rst_n.value = 0
    dut.sclk.value = 0
    dut.mosi.value = 0
    dut.cs_n.value = 1
    dut.tx_data.value = 0
    dut.tx_load.value = 0
    await Timer(50, units="ns")
    dut.rst_n.value = 1
    await Timer(20, units="ns")

    # Load TX
    dut.tx_data.value = 0xCAFE
    dut.tx_load.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    dut.tx_load.value = 0

    # Wait a few clocks
    for _ in range(5):
        await RisingEdge(dut.clk)

    dut._log.info(f"After TX load: miso={int(dut.miso.value)}, cs_n={int(dut.cs_n.value)}")

    # Assert CS
    dut.cs_n.value = 0
    # Wait for sync (5 clocks)
    for _ in range(5):
        await RisingEdge(dut.clk)

    dut._log.info(f"After CS assert: miso={int(dut.miso.value)}")

    # Try reading bit by bit
    for i in range(16):
        dut.sclk.value = 0
        await Timer(50, units="ns")
        dut.sclk.value = 1
        await Timer(50, units="ns")
        bit = int(dut.miso.value)
        dut._log.info(f"Bit {i}: miso={bit}")

