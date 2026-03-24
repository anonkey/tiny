import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_kogge_stone_add_exhaustive_8bit(dut):
  for a in range(256):
    for b in range(256):
      dut.input_A.value = a
      dut.input_B.value = b
      dut.sub.value = 0
      dut.cin.value = 0

      await Timer(1, unit="ns")

      expected = (a + b) & 0x1FF
      observed = int(dut.output_S.value) & 0x1FF

      assert observed == expected, (
        f"ADD mismatch: a={a:#x}, b={b:#x}: "
        f"got={observed:#x}, expected={expected:#x}"
      )


@cocotb.test()
async def test_kogge_stone_sub_exhaustive_8bit(dut):
  for a in range(256):
    for b in range(256):
      dut.input_A.value = a
      dut.input_B.value = b
      dut.sub.value = 1
      dut.cin.value = 0

      await Timer(1, unit="ns")

      expected = (a + (b ^ 0xFF) + 1) & 0x1FF
      observed = int(dut.output_S.value) & 0x1FF

      assert observed == expected, (
        f"SUB mismatch: a={a:#x}, b={b:#x}: "
        f"got={observed:#x}, expected={expected:#x}"
      )


@cocotb.test()
async def test_kogge_stone_cin_add(dut):
  """ADD with cin=1 should compute a + b + 1."""
  edges = [0x00, 0x01, 0x7F, 0x80, 0xFE, 0xFF]
  for a in edges:
    for b in edges:
      dut.input_A.value = a
      dut.input_B.value = b
      dut.sub.value = 0
      dut.cin.value = 1

      await Timer(1, unit="ns")

      expected = (a + b + 1) & 0x1FF
      observed = int(dut.output_S.value) & 0x1FF

      assert observed == expected, (
        f"ADD+cin mismatch: a={a:#x}, b={b:#x}: "
        f"got={observed:#x}, expected={expected:#x}"
      )


@cocotb.test()
async def test_kogge_stone_cin_sub(dut):
  """SUB with cin=1: w_Cin = sub|cin = 1, same result as cin=0 (sub forces cin high)."""
  edges = [0x00, 0x01, 0x7F, 0x80, 0xFE, 0xFF]
  for a in edges:
    for b in edges:
      dut.input_A.value = a
      dut.input_B.value = b
      dut.sub.value = 1
      dut.cin.value = 1

      await Timer(1, unit="ns")

      # w_Cin = sub | cin = 1, same as sub with cin=0
      expected = (a + (b ^ 0xFF) + 1) & 0x1FF
      observed = int(dut.output_S.value) & 0x1FF

      assert observed == expected, (
        f"SUB+cin mismatch: a={a:#x}, b={b:#x}: "
        f"got={observed:#x}, expected={expected:#x}"
      )
