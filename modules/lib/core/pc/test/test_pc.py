import cocotb
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb_helpers import start_clock, reset_sync, tick


async def reset(dut):
  """Reset PC."""
  dut.load.value = 0
  dut.load_addr.value = 0
  dut.en.value = 1
  await reset_sync(dut)


@cocotb.test()
async def test_pc_reset(dut):
  """After reset + first tick, PC should be 1 (0 + 1)."""
  start_clock(dut)
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
  start_clock(dut)
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
  start_clock(dut)
  await reset(dut)

  # Increment 5 times -> PC = 5
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
  start_clock(dut)
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
  start_clock(dut)
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
  start_clock(dut)
  await reset(dut)

  addrs = [0x10, 0x80, 0xFF, 0x00, 0x55]
  for addr in addrs:
    dut.load.value = 1
    dut.load_addr.value = addr
    await tick(dut)
    assert int(dut.pc_out.value) == addr, (
      f"PC should be {addr:#x}, got {int(dut.pc_out.value):#x}"
    )


@cocotb.test()
async def test_pc_hold_when_disabled(dut):
  """PC should not increment when en=0."""
  start_clock(dut)
  await reset(dut)

  # Increment a few times
  for _ in range(3):
    await tick(dut)
  assert int(dut.pc_out.value) == 3

  # Disable PC
  dut.en.value = 0
  for _ in range(5):
    await tick(dut)
  assert int(dut.pc_out.value) == 3, (
    f"PC should hold at 3 when en=0, got {int(dut.pc_out.value)}"
  )


@cocotb.test()
async def test_pc_enable_toggle(dut):
  """PC should only increment on cycles where en=1."""
  start_clock(dut)
  await reset(dut)

  # en=1: PC increments 1,2,3
  for expected in range(1, 4):
    await tick(dut)
    assert int(dut.pc_out.value) == expected

  # en=0: hold at 3
  dut.en.value = 0
  await tick(dut)
  await tick(dut)
  assert int(dut.pc_out.value) == 3

  # en=1 again: resume incrementing
  dut.en.value = 1
  await tick(dut)
  assert int(dut.pc_out.value) == 4, (
    f"PC should resume to 4, got {int(dut.pc_out.value)}"
  )
