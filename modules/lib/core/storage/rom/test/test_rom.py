import cocotb
from cocotb.triggers import Timer
import os


# Expected ROM contents — must match test_rom.hex
ROM_DATA = [0] * 256

# Program: a few instructions at the start
ROM_DATA[0] = 0x1234
ROM_DATA[1] = 0x5678
ROM_DATA[2] = 0x9ABC
ROM_DATA[3] = 0xDEF0
ROM_DATA[4] = 0x0001
ROM_DATA[5] = 0xFFFF
ROM_DATA[6] = 0x0000
ROM_DATA[7] = 0x8000

# Some values at high addresses
ROM_DATA[0xFE] = 0xCAFE
ROM_DATA[0xFF] = 0xBEEF


def generate_hex_file():
  """Generate the hex file that the ROM reads."""
  for path in [os.path.join(os.path.dirname(__file__), "test_rom.hex"), "test_rom.hex"]:
    with open(path, "w") as f:
      for val in ROM_DATA:
        f.write(f"{val:04X}\n")


# Generate hex file before simulation
generate_hex_file()


@cocotb.test()
async def test_rom_sequential_read(dut):
  """Read first 8 addresses sequentially."""
  for addr in range(8):
    dut.addr.value = addr
    await Timer(1, unit="ns")
    observed = int(dut.data.value)
    expected = ROM_DATA[addr]
    assert observed == expected, (
      f"ROM[{addr}] should be {expected:#06x}, got {observed:#06x}"
    )


@cocotb.test()
async def test_rom_high_addresses(dut):
  """Read values at high addresses."""
  for addr in [0xFE, 0xFF]:
    dut.addr.value = addr
    await Timer(1, unit="ns")
    observed = int(dut.data.value)
    expected = ROM_DATA[addr]
    assert observed == expected, (
      f"ROM[{addr:#04x}] should be {expected:#06x}, got {observed:#06x}"
    )


@cocotb.test()
async def test_rom_zero_regions(dut):
  """Uninitialized regions should read as 0."""
  for addr in [10, 50, 100, 200]:
    dut.addr.value = addr
    await Timer(1, unit="ns")
    observed = int(dut.data.value)
    assert observed == 0, (
      f"ROM[{addr}] should be 0x0000, got {observed:#06x}"
    )


@cocotb.test()
async def test_rom_all_addresses(dut):
  """Verify every address in the ROM."""
  for addr in range(256):
    dut.addr.value = addr
    await Timer(1, unit="ns")
    observed = int(dut.data.value)
    expected = ROM_DATA[addr]
    assert observed == expected, (
      f"ROM[{addr:#04x}] should be {expected:#06x}, got {observed:#06x}"
    )


@cocotb.test()
async def test_rom_combinational(dut):
  """ROM output should change immediately with address (no clock needed)."""
  dut.addr.value = 0
  await Timer(1, unit="ns")
  assert int(dut.data.value) == ROM_DATA[0]

  # Change address, output should update after propagation delay
  dut.addr.value = 3
  await Timer(1, unit="ns")
  assert int(dut.data.value) == ROM_DATA[3]

  # Jump to a high address
  dut.addr.value = 0xFF
  await Timer(1, unit="ns")
  assert int(dut.data.value) == ROM_DATA[0xFF]
