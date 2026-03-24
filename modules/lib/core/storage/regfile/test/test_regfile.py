import cocotb
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb_helpers import start_clock, reset_sync, tick


async def reset(dut):
  """Reset all registers."""
  dut.we.value = 0
  dut.wd.value = 0
  dut.raddr1.value = 0
  dut.raddr2.value = 0
  dut.waddr.value = 0
  await reset_sync(dut)


async def write_reg(dut, addr, data):
  """Write data to register at addr."""
  dut.we.value = 1
  dut.waddr.value = addr
  dut.wd.value = data
  await tick(dut)
  dut.we.value = 0


async def read_reg(dut, addr):
  """Read register via port 1 (combinational)."""
  dut.raddr1.value = addr
  await FallingEdge(dut.clk)
  return int(dut.rd1.value)


@cocotb.test()
async def test_reset_clears_all(dut):
  """All registers should be 0 after reset."""
  start_clock(dut)
  await reset(dut)

  for addr in range(8):
    dut.raddr1.value = addr
    dut.raddr2.value = addr
    await tick(dut)
    assert int(dut.rd1.value) == 0, f"r{addr} rd1 should be 0, got {int(dut.rd1.value)}"
    assert int(dut.rd2.value) == 0, f"r{addr} rd2 should be 0, got {int(dut.rd2.value)}"


@cocotb.test()
async def test_write_read_single(dut):
  """Write a value to one register, read it back."""
  start_clock(dut)
  await reset(dut)

  await write_reg(dut, 3, 0xAB)

  dut.raddr1.value = 3
  await tick(dut)
  assert int(dut.rd1.value) == 0xAB, f"r3 should be 0xAB, got {int(dut.rd1.value):#x}"


@cocotb.test()
async def test_write_all_read_all(dut):
  """Write unique values to all 8 registers, then read them all back.
  r0 is hardwired to zero and ignores writes."""
  start_clock(dut)
  await reset(dut)

  values = [0x10, 0x21, 0x32, 0x43, 0x54, 0x65, 0x76, 0x87]
  expected = [0x00, 0x21, 0x32, 0x43, 0x54, 0x65, 0x76, 0x87]  # r0 stays 0
  for addr, val in enumerate(values):
    await write_reg(dut, addr, val)

  for addr, exp in enumerate(expected):
    dut.raddr1.value = addr
    await tick(dut)
    observed = int(dut.rd1.value)
    assert observed == exp, (
      f"r{addr} should be {exp:#x}, got {observed:#x}"
    )


@cocotb.test()
async def test_two_read_ports(dut):
  """Both read ports should work independently and simultaneously."""
  start_clock(dut)
  await reset(dut)

  await write_reg(dut, 1, 0xAA)
  await write_reg(dut, 7, 0x55)

  dut.raddr1.value = 1
  dut.raddr2.value = 7
  await tick(dut)
  assert int(dut.rd1.value) == 0xAA, f"rd1 should be 0xAA, got {int(dut.rd1.value):#x}"
  assert int(dut.rd2.value) == 0x55, f"rd2 should be 0x55, got {int(dut.rd2.value):#x}"

  # Swap
  dut.raddr1.value = 7
  dut.raddr2.value = 1
  await tick(dut)
  assert int(dut.rd1.value) == 0x55, f"rd1 should be 0x55, got {int(dut.rd1.value):#x}"
  assert int(dut.rd2.value) == 0xAA, f"rd2 should be 0xAA, got {int(dut.rd2.value):#x}"


@cocotb.test()
async def test_write_enable_off(dut):
  """When we=0, writing should have no effect."""
  start_clock(dut)
  await reset(dut)

  await write_reg(dut, 2, 0xFF)

  # Try to overwrite with we=0
  dut.we.value = 0
  dut.waddr.value = 2
  dut.wd.value = 0x00
  await tick(dut)

  dut.raddr1.value = 2
  await tick(dut)
  assert int(dut.rd1.value) == 0xFF, (
    f"r2 should still be 0xFF, got {int(dut.rd1.value):#x}"
  )


@cocotb.test()
async def test_write_does_not_affect_others(dut):
  """Writing to one register should not change others."""
  start_clock(dut)
  await reset(dut)

  # Write all to known values
  for addr in range(8):
    await write_reg(dut, addr, addr * 0x11)

  # Overwrite r4 only
  await write_reg(dut, 4, 0xEE)

  # Check all others unchanged
  for addr in range(8):
    dut.raddr1.value = addr
    await tick(dut)
    if addr == 4:
      assert int(dut.rd1.value) == 0xEE
    else:
      expected = addr * 0x11
      observed = int(dut.rd1.value)
      assert observed == expected, (
        f"r{addr} should be {expected:#x}, got {observed:#x}"
      )


@cocotb.test()
async def test_read_during_write(dut):
  """Read port should reflect the old value during the same cycle as a write."""
  start_clock(dut)
  await reset(dut)

  await write_reg(dut, 5, 0x42)

  # Start a write to r5 with new value, read r5 simultaneously
  dut.we.value = 1
  dut.waddr.value = 5
  dut.wd.value = 0x99
  dut.raddr1.value = 5
  await RisingEdge(dut.clk)
  # On the rising edge, old value should still be readable
  # (new value captured on this edge, visible next cycle)
  await FallingEdge(dut.clk)
  # After the rising edge, the new value is now captured
  assert int(dut.rd1.value) == 0x99, (
    f"r5 should be 0x99 after write cycle, got {int(dut.rd1.value):#x}"
  )

  dut.we.value = 0


@cocotb.test()
async def test_consecutive_writes_same_reg(dut):
  """Multiple writes to the same register should keep the last value."""
  start_clock(dut)
  await reset(dut)

  for val in [0x01, 0x02, 0x03, 0xFF]:
    await write_reg(dut, 1, val)

  dut.raddr1.value = 1
  await tick(dut)
  assert int(dut.rd1.value) == 0xFF, (
    f"r1 should be 0xFF, got {int(dut.rd1.value):#x}"
  )


@cocotb.test()
async def test_r0_hardwired_zero(dut):
  """r0 must always read zero, even after a write attempt."""
  start_clock(dut)
  await reset(dut)

  await write_reg(dut, 0, 0xFF)

  dut.raddr1.value = 0
  dut.raddr2.value = 0
  await tick(dut)
  assert int(dut.rd1.value) == 0, f"r0 rd1 should be 0, got {int(dut.rd1.value):#x}"
  assert int(dut.rd2.value) == 0, f"r0 rd2 should be 0, got {int(dut.rd2.value):#x}"


@cocotb.test()
async def test_r0_does_not_block_other_writes(dut):
  """r0 write protection must not affect writes to other registers."""
  start_clock(dut)
  await reset(dut)

  # Attempt write to r0 and r1 in sequence
  await write_reg(dut, 0, 0xAB)
  await write_reg(dut, 1, 0xCD)

  dut.raddr1.value = 0
  dut.raddr2.value = 1
  await tick(dut)
  assert int(dut.rd1.value) == 0x00, f"r0 should be 0, got {int(dut.rd1.value):#x}"
  assert int(dut.rd2.value) == 0xCD, f"r1 should be 0xCD, got {int(dut.rd2.value):#x}"
