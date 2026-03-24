import cocotb
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb_helpers import start_clock, reset_sync, tick


async def reset(dut):
  dut.sclk_rise.value = 0
  dut.cs_n.value = 1
  dut.rx_shift.value = 0
  await reset_sync(dut)


async def pulse_sclk_rise(dut):
  """Simulate one SCLK rising edge detection pulse."""
  dut.sclk_rise.value = 1
  await tick(dut)
  dut.sclk_rise.value = 0


@cocotb.test()
async def test_reset(dut):
  """After reset, byte_done=0 and rx_data=0."""
  start_clock(dut)
  await reset(dut)
  assert int(dut.byte_done.value) == 0
  assert int(dut.rx_data.value) == 0


@cocotb.test()
async def test_count_to_byte_done(dut):
  """8 sclk_rise pulses should trigger byte_done."""
  start_clock(dut)
  await reset(dut)

  dut.cs_n.value = 0
  await tick(dut)

  # First 7 pulses: no byte_done
  for i in range(7):
    await pulse_sclk_rise(dut)
    assert int(dut.byte_done.value) == 0, f"byte_done should be 0 after {i+1} pulses"

  # 8th pulse: byte_done should fire (registered, visible next cycle)
  await pulse_sclk_rise(dut)
  await tick(dut)  # let registered byte_done propagate
  assert int(dut.byte_done.value) == 1, "byte_done should be 1 after 8 pulses"


@cocotb.test()
async def test_rx_latch(dut):
  """rx_data should latch rx_shift at byte boundary."""
  start_clock(dut)
  await reset(dut)

  dut.cs_n.value = 0
  await tick(dut)

  # Shift in 8 bits, set rx_shift to 0xA5 before the 8th pulse
  dut.rx_shift.value = 0xA5
  for _ in range(8):
    await pulse_sclk_rise(dut)

  await tick(dut)
  assert int(dut.rx_data.value) == 0xA5, \
    f"rx_data should be 0xA5, got {int(dut.rx_data.value):#04x}"


@cocotb.test()
async def test_auto_reset(dut):
  """Counter should auto-reset after reaching BYTE_WIDTH."""
  start_clock(dut)
  await reset(dut)

  dut.cs_n.value = 0
  await tick(dut)

  # First byte: 8 pulses
  dut.rx_shift.value = 0x11
  for _ in range(8):
    await pulse_sclk_rise(dut)
  await tick(dut)
  assert int(dut.rx_data.value) == 0x11

  # Second byte: 8 more pulses (counter should have auto-reset)
  dut.rx_shift.value = 0x22
  for _ in range(8):
    await pulse_sclk_rise(dut)
  await tick(dut)
  assert int(dut.rx_data.value) == 0x22, \
    f"rx_data should be 0x22 (second byte), got {int(dut.rx_data.value):#04x}"


@cocotb.test()
async def test_cs_deassert_reset(dut):
  """Counter should reset when CS goes high."""
  start_clock(dut)
  await reset(dut)

  dut.cs_n.value = 0
  await tick(dut)

  # Send 4 pulses (partial byte)
  for _ in range(4):
    await pulse_sclk_rise(dut)

  # Deassert CS
  dut.cs_n.value = 1
  await tick(dut)
  await tick(dut)

  # Reassert CS and send 8 pulses — should get a clean byte
  dut.cs_n.value = 0
  await tick(dut)

  dut.rx_shift.value = 0xBB
  for _ in range(8):
    await pulse_sclk_rise(dut)
  await tick(dut)
  assert int(dut.rx_data.value) == 0xBB, \
    f"expected 0xBB after CS reassert, got {int(dut.rx_data.value):#04x}"


@cocotb.test()
async def test_partial_byte_no_done(dut):
  """4 pulses then CS high should not trigger byte_done."""
  start_clock(dut)
  await reset(dut)

  dut.cs_n.value = 0
  await tick(dut)

  for _ in range(4):
    await pulse_sclk_rise(dut)
    assert int(dut.byte_done.value) == 0, "byte_done should not fire on partial byte"

  dut.cs_n.value = 1
  await tick(dut)
  await tick(dut)
  assert int(dut.byte_done.value) == 0, "byte_done should not fire after CS deassert"


@cocotb.test()
async def test_multi_byte(dut):
  """Two consecutive bytes should each produce byte_done."""
  start_clock(dut)
  await reset(dut)

  dut.cs_n.value = 0
  await tick(dut)

  done_count = 0
  for byte_num in range(2):
    dut.rx_shift.value = (byte_num + 1) * 0x11
    for _ in range(8):
      await pulse_sclk_rise(dut)
    await tick(dut)
    if int(dut.byte_done.value) == 1:
      done_count += 1

  assert done_count == 2, f"expected 2 byte_done pulses, got {done_count}"
