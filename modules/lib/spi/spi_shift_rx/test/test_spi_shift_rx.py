import cocotb
from cocotb.triggers import RisingEdge
from cocotb_helpers import start_clock, reset_sync, tick


async def reset(dut):
  dut.bit_in.value = 0
  dut.shift_en.value = 0
  await reset_sync(dut)


async def shift_bit(dut, bit_val):
  """Shift in a single bit."""
  dut.bit_in.value = bit_val
  dut.shift_en.value = 1
  await tick(dut)
  dut.shift_en.value = 0


async def shift_byte(dut, byte_val):
  """Shift in 8 bits MSB-first."""
  for i in range(7, -1, -1):
    bit = (byte_val >> i) & 1
    await shift_bit(dut, bit)


@cocotb.test()
async def test_reset(dut):
  """After reset, o_data should be 0."""
  start_clock(dut)
  await reset(dut)
  assert int(dut.data.value) == 0


@cocotb.test()
async def test_shift_in_0xa5(dut):
  """Shift in 0xA5 (10100101) MSB-first and verify assembled byte."""
  start_clock(dut)
  await reset(dut)

  await shift_byte(dut, 0xA5)
  assert int(dut.data.value) == 0xA5, \
    f"expected 0xA5, got {int(dut.data.value):#04x}"


@cocotb.test()
async def test_shift_en_gating(dut):
  """Data should not shift when i_shift_en=0."""
  start_clock(dut)
  await reset(dut)

  # Shift in 4 bits of 0xA5 (1010)
  for i in range(7, 3, -1):
    bit = (0xA5 >> i) & 1
    await shift_bit(dut, bit)

  # Present a bit but keep shift_en=0 for several cycles
  dut.bit_in.value = 1
  dut.shift_en.value = 0
  for _ in range(4):
    await tick(dut)

  # Value should still be just the 4 bits shifted in: 0000_1010 = 0x0A
  # (bits enter at LSB and shift left, so after 4 shifts of 1,0,1,0: 00001010)
  val = int(dut.data.value)
  assert val == 0x0A, \
    f"shift_en=0 should prevent shifting, expected 0x0A, got {val:#04x}"


@cocotb.test()
async def test_msb_first_order(dut):
  """Verify bit order: first bit shifted in ends up as MSB."""
  start_clock(dut)
  await reset(dut)

  # Shift in 1 followed by 7 zeros
  await shift_bit(dut, 1)
  for _ in range(7):
    await shift_bit(dut, 0)

  assert int(dut.data.value) == 0x80, \
    f"first bit should be MSB, expected 0x80, got {int(dut.data.value):#04x}"


@cocotb.test()
async def test_multiple_consecutive_bytes(dut):
  """Shift in two consecutive bytes and verify the second overwrites the first."""
  start_clock(dut)
  await reset(dut)

  # First byte
  await shift_byte(dut, 0x3C)
  assert int(dut.data.value) == 0x3C, \
    f"first byte: expected 0x3C, got {int(dut.data.value):#04x}"

  # Second byte — shifts through the same register
  await shift_byte(dut, 0xF0)
  assert int(dut.data.value) == 0xF0, \
    f"second byte: expected 0xF0, got {int(dut.data.value):#04x}"


@cocotb.test()
async def test_shift_in_0xff(dut):
  """Shift in 0xFF — all ones."""
  start_clock(dut)
  await reset(dut)

  await shift_byte(dut, 0xFF)
  assert int(dut.data.value) == 0xFF, \
    f"expected 0xFF, got {int(dut.data.value):#04x}"


@cocotb.test()
async def test_shift_in_0x00(dut):
  """Shift in 0x00 — all zeros."""
  start_clock(dut)
  await reset(dut)

  await shift_byte(dut, 0x00)
  assert int(dut.data.value) == 0x00, \
    f"expected 0x00, got {int(dut.data.value):#04x}"
