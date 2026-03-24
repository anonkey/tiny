import cocotb
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb_helpers import start_clock, reset_sync, tick
from cocotb_helpers.isa import (
  enc_r, enc_imm6, enc_imm8, enc_bez,
  OP_ADD, OP_LDI, OP_JMP, OP_LOAD, OP_STORE, OP_BEZ, OP_NOP,
)
from cocotb_helpers.spi import (
  spi_clock_byte, CMD_IFETCH, CMD_LOAD, CMD_STORE, CMD_WREN,
)


SYS_CLK_PERIOD = 10  # ns
SCLK_DIV = 5         # sys clocks per SCLK half-period


async def reset(dut):
  dut.sclk.value = 0
  dut.miso.value = 0
  await reset_sync(dut, clk_cycles=5)


async def wait_cs_low(dut, timeout=500):
  for _ in range(timeout):
    await RisingEdge(dut.clk)
    if int(dut.cs_n.value) == 0:
      await FallingEdge(dut.clk)
      return
  raise TimeoutError("cs_n never went low")


async def wait_cs_high(dut, timeout=500):
  for _ in range(timeout):
    await RisingEdge(dut.clk)
    if int(dut.cs_n.value) == 1:
      await FallingEdge(dut.clk)
      return
  raise TimeoutError("cs_n never went high")


async def inter_byte_gap(dut):
  """Wait for byte_done to propagate through synchronizer pipeline
  and mem_ctrl to load the next TX byte into spi_phy.
  Pipeline: SCLK sync (2clk) + bit_cnt (1) + byte_done reg (1)
  + mem_ctrl transition (1) + tx_load (1) + spi_phy load (1) = ~7 clocks"""
  await tick(dut, 15)


async def do_fetch_cycle(dut, instruction, expected_pc=None):
  """Respond to a full FETCH: [CMD] [ADDR] [rx_hi] [rx_lo]."""
  await wait_cs_low(dut)

  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_IFETCH, f"expected IFETCH 0x03, got {cmd:#04x}"
  await inter_byte_gap(dut)

  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  if expected_pc is not None:
    assert addr == expected_pc, f"expected PC={expected_pc:#04x}, got addr={addr:#04x}"
  await inter_byte_gap(dut)

  await spi_clock_byte(dut, (instruction >> 8) & 0xFF, sclk_div=SCLK_DIV)
  await inter_byte_gap(dut)

  await spi_clock_byte(dut, instruction & 0xFF, sclk_div=SCLK_DIV)
  # Last byte -- wait for CS high instead of inter-byte gap
  await wait_cs_high(dut)

  return addr


@cocotb.test()
async def test_nop(dut):
  """Fetch NOP, verify PC advances from 0 to 1."""
  start_clock(dut)
  await reset(dut)

  nop = enc_r(OP_NOP, 0, 0, 0)
  await do_fetch_cycle(dut, nop, expected_pc=0)

  # Next fetch
  await wait_cs_low(dut)
  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_IFETCH
  await inter_byte_gap(dut)
  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert addr == 1, f"PC should be 1 after NOP, got {addr}"


@cocotb.test()
async def test_ldi(dut):
  """LDI r0, 0x42 -- verify PC advances."""
  start_clock(dut)
  await reset(dut)

  await do_fetch_cycle(dut, enc_imm8(OP_LDI, 0, 0x42), expected_pc=0)

  await wait_cs_low(dut)
  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_IFETCH
  await inter_byte_gap(dut)
  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert addr == 1, f"PC should advance to 1, got {addr}"


@cocotb.test()
async def test_add(dut):
  """LDI r0, 3 ; LDI r1, 5 ; ADD r2, r0, r1."""
  start_clock(dut)
  await reset(dut)

  await do_fetch_cycle(dut, enc_imm8(OP_LDI, 0, 3), expected_pc=0)
  await do_fetch_cycle(dut, enc_imm8(OP_LDI, 1, 5), expected_pc=1)
  await do_fetch_cycle(dut, enc_r(OP_ADD, 2, 0, 1), expected_pc=2)

  await wait_cs_low(dut)
  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_IFETCH
  await inter_byte_gap(dut)
  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert addr == 3, f"PC should be 3, got {addr}"


@cocotb.test()
async def test_jmp(dut):
  """JMP 0x10 -- verify PC jumps."""
  start_clock(dut)
  await reset(dut)

  await do_fetch_cycle(dut, enc_imm8(OP_JMP, 0, 0x10), expected_pc=0)

  await wait_cs_low(dut)
  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_IFETCH
  await inter_byte_gap(dut)
  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert addr == 0x10, f"PC should jump to 0x10, got {addr:#04x}"


@cocotb.test()
async def test_load(dut):
  """LOAD r0, [r1 + 2] -- verify SPI FAST_READ protocol."""
  start_clock(dut)
  await reset(dut)

  await do_fetch_cycle(dut, enc_imm8(OP_LDI, 1, 0x30), expected_pc=0)

  load_instr = enc_imm6(OP_LOAD, 0, 1, 2)
  await do_fetch_cycle(dut, load_instr, expected_pc=1)

  # FAST_READ transaction
  await wait_cs_low(dut)

  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_LOAD, f"expected 0x0B, got {cmd:#04x}"
  await inter_byte_gap(dut)

  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert addr == 0x32, f"expected addr 0x32, got {addr:#04x}"
  await inter_byte_gap(dut)

  await spi_clock_byte(dut, sclk_div=SCLK_DIV)  # DUMMY
  await inter_byte_gap(dut)

  await spi_clock_byte(dut, 0xAB, sclk_div=SCLK_DIV)  # data response
  await wait_cs_high(dut)

  # Next fetch at PC=2
  await wait_cs_low(dut)
  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_IFETCH
  await inter_byte_gap(dut)
  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert addr == 2, f"PC should be 2, got {addr}"


@cocotb.test()
async def test_store(dut):
  """STORE [r2 + 4], r1 -- verify WREN + WRITE protocol."""
  start_clock(dut)
  await reset(dut)

  # STORE I-type: [1110][rd:3][rs1:3][imm6:6]
  # rs1 = base address register, imm6[5:3] selects data source via rs2 read port,
  # imm6[2:0] is the offset added to rs1.
  # r0 is hardwired to zero — use r1 for data, r2 for base addr.
  await do_fetch_cycle(dut, enc_imm8(OP_LDI, 1, 0x55), expected_pc=0)
  await do_fetch_cycle(dut, enc_imm8(OP_LDI, 2, 0x20), expected_pc=1)

  # imm6 = (data_reg << 3) | offset: data from r1, offset bits [2:0] = 4
  # Full imm6 = (1 << 3) | 4 = 0x0C, so address = 0x20 + 0x0C = 0x2C
  store_instr = enc_imm6(OP_STORE, 1, 2, (1 << 3) | 4)
  await do_fetch_cycle(dut, store_instr, expected_pc=2)

  # WREN CS cycle
  await wait_cs_low(dut)
  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_WREN, f"expected WREN 0x06, got {cmd:#04x}"
  await wait_cs_high(dut)

  # WRITE CS cycle
  await wait_cs_low(dut)
  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_STORE, f"expected WRITE 0x02, got {cmd:#04x}"
  await inter_byte_gap(dut)

  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert addr == 0x2C, f"expected addr 0x2C, got {addr:#04x}"
  await inter_byte_gap(dut)

  data = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert data == 0x55, f"expected data 0x55, got {data:#04x}"
  await wait_cs_high(dut)

  # Next fetch at PC=3
  await wait_cs_low(dut)
  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_IFETCH
  await inter_byte_gap(dut)
  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert addr == 3, f"PC should be 3, got {addr}"


@cocotb.test()
async def test_bez_taken(dut):
  """BEZ branches when rs1 == 0 (use r0, which is hardwired to zero)."""
  start_clock(dut)
  await reset(dut)

  # r0 is always 0 — BEZ r0 should always branch
  await do_fetch_cycle(dut, enc_r(OP_NOP, 0, 0, 0), expected_pc=0)

  # BEZ r0, 0x10
  await do_fetch_cycle(dut, enc_bez(0, 0x10), expected_pc=1)

  # Next fetch should be at PC=0x10 (branch taken)
  await wait_cs_low(dut)
  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_IFETCH
  await inter_byte_gap(dut)
  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert addr == 0x10, f"PC should jump to 0x10 after BEZ (r0==0), got {addr:#04x}"


@cocotb.test()
async def test_bez_not_taken(dut):
  """BEZ does not branch when rs1 != 0."""
  start_clock(dut)
  await reset(dut)

  # Use r1 for non-zero value (r0 is hardwired to zero)
  await do_fetch_cycle(dut, enc_imm8(OP_LDI, 1, 42), expected_pc=0)

  # BEZ r1, 0x10
  await do_fetch_cycle(dut, enc_bez(1, 0x10), expected_pc=1)

  # Next fetch should be at PC=2 (fall through, not taken)
  await wait_cs_low(dut)
  cmd = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert cmd == CMD_IFETCH
  await inter_byte_gap(dut)
  addr = await spi_clock_byte(dut, sclk_div=SCLK_DIV)
  assert addr == 2, f"PC should be 2 (fall through, r1!=0), got {addr:#04x}"
