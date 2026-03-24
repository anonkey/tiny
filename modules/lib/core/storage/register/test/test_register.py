import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotb_helpers import start_clock, reset_async
import random


async def reset(dut):
  dut.D.value = 0
  dut.en.value = 0
  await reset_async(dut)


@cocotb.test()
async def test_register_reset(dut):
  """All bits should be 0 after reset."""
  start_clock(dut)
  dut.rst_n.value = 0
  dut.D.value = 0xFF
  dut.en.value = 1
  await Timer(10, unit="ns")

  assert int(dut.Q.value) == 0, f"Q should be 0x00 after reset, got {int(dut.Q.value):#04x}"


@cocotb.test()
async def test_register_load(dut):
  """Register should capture D on rising edge when en=1."""
  start_clock(dut)
  await reset(dut)

  dut.en.value = 1
  dut.D.value = 0xA5
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")

  assert int(dut.Q.value) == 0xA5, f"Q should be 0xA5, got {int(dut.Q.value):#04x}"


@cocotb.test()
async def test_register_hold(dut):
  """Register should hold value when en=0."""
  start_clock(dut)
  await reset(dut)

  # Load a value
  dut.en.value = 1
  dut.D.value = 0x42
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")
  assert int(dut.Q.value) == 0x42

  # Disable, change D
  dut.en.value = 0
  dut.D.value = 0xFF
  await RisingEdge(dut.clk)
  await Timer(2, unit="ns")

  assert int(dut.Q.value) == 0x42, f"Q should hold at 0x42, got {int(dut.Q.value):#04x}"


@cocotb.test()
async def test_register_sequential(dut):
  """Load multiple values in sequence."""
  start_clock(dut)
  await reset(dut)
  dut.en.value = 1

  values = [0x00, 0xFF, 0xA5, 0x5A, 0x0F, 0xF0, 0x01, 0x80]
  for val in values:
    dut.D.value = val
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")
    assert int(dut.Q.value) == val, f"Q should be {val:#04x}, got {int(dut.Q.value):#04x}"


@cocotb.test()
async def test_register_random(dut):
  """Random load/hold patterns."""
  start_clock(dut)
  await reset(dut)

  random.seed(42)
  held_val = 0

  for _ in range(100):
    en = random.randint(0, 1)
    d = random.randint(0, 255)

    dut.en.value = en
    dut.D.value = d
    await RisingEdge(dut.clk)
    await Timer(2, unit="ns")

    if en:
      held_val = d

    assert int(dut.Q.value) == held_val, (
      f"en={en}, D={d:#04x}: Q should be {held_val:#04x}, got {int(dut.Q.value):#04x}"
    )
