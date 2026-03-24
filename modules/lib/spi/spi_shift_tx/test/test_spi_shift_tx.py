import cocotb
from cocotb.triggers import RisingEdge
from cocotb_helpers import start_clock, reset_sync, tick


async def reset(dut):
  dut.data.value = 0
  dut.load.value = 0
  dut.shift_en.value = 0
  dut.active.value = 0
  await reset_sync(dut)


async def load_byte(dut, byte_val):
  """Load a byte into the TX shift register."""
  dut.data.value = byte_val
  dut.load.value = 1
  await tick(dut)
  dut.load.value = 0


async def shift_one(dut):
  """Pulse shift_en for one clock cycle."""
  dut.shift_en.value = 1
  await tick(dut)
  dut.shift_en.value = 0


async def consume_guard(dut):
  """Wait one cycle for the load guard to clear."""
  await tick(dut)


@cocotb.test()
async def test_reset(dut):
  """After reset, miso should be 0."""
  start_clock(dut)
  await reset(dut)
  assert int(dut.miso.value) == 0


@cocotb.test()
async def test_miso_zero_when_inactive(dut):
  """o_miso should be 0 when i_active=0, even with data loaded."""
  start_clock(dut)
  await reset(dut)

  await load_byte(dut, 0xFF)
  dut.active.value = 0
  await tick(dut)
  assert int(dut.miso.value) == 0, "miso should be 0 when inactive"


@cocotb.test()
async def test_shift_out_msb_first(dut):
  """Load 0xA5 (10100101) and shift out all 8 bits MSB-first."""
  start_clock(dut)
  await reset(dut)

  dut.active.value = 1
  await load_byte(dut, 0xA5)
  # Guard cycle: first shift_en after load is suppressed.
  # consume it so subsequent shifts work correctly.
  await consume_guard(dut)

  expected_bits = [1, 0, 1, 0, 0, 1, 0, 1]  # 0xA5 MSB-first

  for i, expected in enumerate(expected_bits):
    assert int(dut.miso.value) == expected, \
      f"bit {i}: expected {expected}, got {int(dut.miso.value)}"
    if i < 7:
      await shift_one(dut)


@cocotb.test()
async def test_load_guard(dut):
  """shift_en on the clock after load should be suppressed (guard FF)."""
  start_clock(dut)
  await reset(dut)

  dut.active.value = 1
  await load_byte(dut, 0xA5)

  # Immediately assert shift_en — the guard should suppress it
  dut.shift_en.value = 1
  await tick(dut)
  dut.shift_en.value = 0

  # MSB should still be 1 (bit 7 of 0xA5) — no shift happened
  assert int(dut.miso.value) == 1, \
    "guard should suppress shift_en on cycle after load"

  # Now a real shift should work
  await shift_one(dut)
  # After one shift, bit 6 of 0xA5 (0) should be on miso
  assert int(dut.miso.value) == 0, \
    f"after first real shift, expected bit6=0, got {int(dut.miso.value)}"


@cocotb.test()
async def test_reload_mid_byte(dut):
  """Partial shift, reload, verify output restarts from new data."""
  start_clock(dut)
  await reset(dut)

  dut.active.value = 1

  # Load 0xFF and shift out 3 bits
  await load_byte(dut, 0xFF)
  await consume_guard(dut)
  for _ in range(3):
    await shift_one(dut)

  # Reload with 0x55 (01010101)
  await load_byte(dut, 0x55)
  await consume_guard(dut)

  expected_bits = [0, 1, 0, 1, 0, 1, 0, 1]  # 0x55 MSB-first
  for i, expected in enumerate(expected_bits):
    assert int(dut.miso.value) == expected, \
      f"after reload, bit {i}: expected {expected}, got {int(dut.miso.value)}"
    if i < 7:
      await shift_one(dut)


@cocotb.test()
async def test_full_byte_0x00(dut):
  """Shift out 0x00 — all bits should be 0."""
  start_clock(dut)
  await reset(dut)

  dut.active.value = 1
  await load_byte(dut, 0x00)
  await consume_guard(dut)

  for i in range(8):
    assert int(dut.miso.value) == 0, \
      f"bit {i}: expected 0 for 0x00"
    if i < 7:
      await shift_one(dut)


@cocotb.test()
async def test_full_byte_0xff(dut):
  """Shift out 0xFF — all bits should be 1."""
  start_clock(dut)
  await reset(dut)

  dut.active.value = 1
  await load_byte(dut, 0xFF)
  await consume_guard(dut)

  for i in range(8):
    assert int(dut.miso.value) == 1, \
      f"bit {i}: expected 1 for 0xFF"
    if i < 7:
      await shift_one(dut)
