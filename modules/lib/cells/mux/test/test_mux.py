import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_mux_8way_select_all(dut):
  """Each select value should pick the correct 8-bit input."""
  # Load 8 distinct values into the 64-bit input bus
  # in[7:0]=0x10, in[15:8]=0x21, ..., in[63:56]=0x87
  values = [0x10 + i * 0x11 for i in range(8)]
  packed = 0
  for i, v in enumerate(values):
    packed |= v << (i * 8)

  dut.data_in.value = packed

  for sel in range(8):
    dut.ctrl.value = sel
    await Timer(1, unit="ns")
    observed = int(dut.out.value)
    expected = values[sel]
    assert observed == expected, (
      f"sel={sel}: expected {expected:#04x}, got {observed:#04x}"
    )


@cocotb.test()
async def test_mux_8way_all_same(dut):
  """When all inputs are the same, output should always match."""
  val = 0xAB
  packed = 0
  for i in range(8):
    packed |= val << (i * 8)

  dut.data_in.value = packed

  for sel in range(8):
    dut.ctrl.value = sel
    await Timer(1, unit="ns")
    observed = int(dut.out.value)
    assert observed == val, (
      f"sel={sel}: expected {val:#04x}, got {observed:#04x}"
    )


@cocotb.test()
async def test_mux_8way_one_hot_inputs(dut):
  """Only one input is nonzero; verify only that select returns it."""
  for active in range(8):
    packed = 0xFF << (active * 8)
    dut.data_in.value = packed

    for sel in range(8):
      dut.ctrl.value = sel
      await Timer(1, unit="ns")
      observed = int(dut.out.value)
      expected = 0xFF if sel == active else 0x00
      assert observed == expected, (
        f"active={active}, sel={sel}: expected {expected:#04x}, got {observed:#04x}"
      )
