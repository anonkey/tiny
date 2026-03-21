import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

SYS_CLK_PERIOD = 10

@cocotb.test()
async def test_probe(dut):
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())

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

    # Wait several clocks
    for _ in range(5):
        await RisingEdge(dut.clk)
    await Timer(1, units="ns")

    # Probe internals
    try:
        tx = int(dut.dut.w_tx_shift.value)
        dut._log.info(f"w_tx_shift = {tx:#06x}")
    except Exception as e:
        dut._log.info(f"Cannot read w_tx_shift: {e}")

    try:
        cs = int(dut.dut.w_cs_sync1.value)
        dut._log.info(f"w_cs_sync1 = {cs}")
    except Exception as e:
        dut._log.info(f"Cannot read w_cs_sync1: {e}")

    try:
        cs_a1 = int(dut.dut.w_cs_active1.value)
        dut._log.info(f"w_cs_active1 = {cs_a1}")
    except Exception as e:
        dut._log.info(f"Cannot read w_cs_active1: {e}")

    dut._log.info(f"miso = {int(dut.miso.value)}")
    dut._log.info(f"cs_n = {int(dut.cs_n.value)}")

    # Assert CS
    dut.cs_n.value = 0
    for _ in range(6):
        await RisingEdge(dut.clk)
    await Timer(1, units="ns")

    try:
        cs = int(dut.dut.w_cs_sync1.value)
        dut._log.info(f"After CS low: w_cs_sync1 = {cs}")
    except Exception as e:
        dut._log.info(f"Cannot read w_cs_sync1: {e}")

    dut._log.info(f"After CS low: miso = {int(dut.miso.value)}")

    try:
        tx = int(dut.dut.w_tx_shift.value)
        dut._log.info(f"After CS low: w_tx_shift = {tx:#06x}")
    except Exception as e:
        dut._log.info(f"Cannot read w_tx_shift: {e}")
