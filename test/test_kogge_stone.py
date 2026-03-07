import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_kogge_stone_add_exhaustive_4bit(dut):
    for a in range(16):
        for b in range(16):
            dut.input_A.value = a
            dut.input_B.value = b
            dut.sub.value = 0

            await Timer(1, units="ns")

            expected = (a + b) & 0x1F
            observed = int(dut.output_S.value) & 0x1F

            assert observed == expected, (
                f"ADD mismatch: a={a:#x}, b={b:#x}: "
                f"got={observed:#x}, expected={expected:#x}"
            )


@cocotb.test()
async def test_kogge_stone_sub_exhaustive_4bit(dut):
    for a in range(16):
        for b in range(16):
            dut.input_A.value = a
            dut.input_B.value = b
            dut.sub.value = 1

            await Timer(1, units="ns")

            expected = (a + (b ^ 0xF) + 1) & 0x1F
            observed = int(dut.output_S.value) & 0x1F

            assert observed == expected, (
                f"SUB mismatch: a={a:#x}, b={b:#x}: "
                f"got={observed:#x}, expected={expected:#x}"
            )
