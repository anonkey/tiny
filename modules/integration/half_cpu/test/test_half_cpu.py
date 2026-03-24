import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge


# --- Instruction encoding helpers ---
def enc_r(opcode, rd, rs1, rs2):
    return (opcode << 12) | (rd << 9) | (rs1 << 6) | (rs2 << 3)

def enc_imm6(opcode, rd, rs1, imm6):
    return (opcode << 12) | (rd << 9) | (rs1 << 6) | (imm6 & 0x3F)

def enc_imm8(opcode, rd, imm8):
    return (opcode << 12) | (rd << 9) | ((imm8 & 0xFF) << 1)

# Opcodes
OP_ADD   = 0x0
OP_LDI   = 0xA
OP_JMP   = 0xB
OP_LOAD  = 0xD
OP_STORE = 0xE
OP_NOP   = 0xF

# SPI commands
CMD_IFETCH = 0x03
CMD_LOAD   = 0x0B
CMD_STORE  = 0x02
CMD_WREN   = 0x06

SYS_CLK_PERIOD = 10  # ns
SCLK_DIV = 5         # sys clocks per SCLK half-period


async def reset(dut):
    dut.rst_n.value = 0
    dut.sclk.value = 0
    dut.miso.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1


async def tick(dut, n=1):
    for _ in range(n):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)


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


async def spi_clock_byte(dut, tx_byte=0x00):
    """Clock one SPI byte using system-clock-derived SCLK.
    Does NOT include inter-byte gap — caller handles timing."""
    received = 0
    for i in range(7, -1, -1):
        dut.miso.value = (tx_byte >> i) & 1
        dut.sclk.value = 0
        await tick(dut, SCLK_DIV)
        dut.sclk.value = 1
        await tick(dut, SCLK_DIV)
        received = (received << 1) | int(dut.mosi.value)
    dut.sclk.value = 0
    return received


async def inter_byte_gap(dut):
    """Wait for byte_done to propagate through synchronizer pipeline
    and mem_ctrl to load the next TX byte into spi_phy.
    Pipeline: SCLK sync (2clk) + bit_cnt (1) + byte_done reg (1)
    + mem_ctrl transition (1) + tx_load (1) + spi_phy load (1) = ~7 clocks"""
    await tick(dut, 15)


async def do_fetch_cycle(dut, instruction, expected_pc=None):
    """Respond to a full FETCH: [CMD] [ADDR] [rx_hi] [rx_lo]."""
    await wait_cs_low(dut)

    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_IFETCH, f"expected IFETCH 0x03, got {cmd:#04x}"
    await inter_byte_gap(dut)

    addr = await spi_clock_byte(dut)
    if expected_pc is not None:
        assert addr == expected_pc, f"expected PC={expected_pc:#04x}, got addr={addr:#04x}"
    await inter_byte_gap(dut)

    await spi_clock_byte(dut, (instruction >> 8) & 0xFF)
    await inter_byte_gap(dut)

    await spi_clock_byte(dut, instruction & 0xFF)
    # Last byte — wait for CS high instead of inter-byte gap
    await wait_cs_high(dut)

    return addr


@cocotb.test()
async def test_nop(dut):
    """Fetch NOP, verify PC advances from 0 to 1."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    nop = enc_r(OP_NOP, 0, 0, 0)
    await do_fetch_cycle(dut, nop, expected_pc=0)

    # Next fetch
    await wait_cs_low(dut)
    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_IFETCH
    await inter_byte_gap(dut)
    addr = await spi_clock_byte(dut)
    assert addr == 1, f"PC should be 1 after NOP, got {addr}"


@cocotb.test()
async def test_ldi(dut):
    """LDI r0, 0x42 — verify PC advances."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 0, 0x42), expected_pc=0)

    await wait_cs_low(dut)
    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_IFETCH
    await inter_byte_gap(dut)
    addr = await spi_clock_byte(dut)
    assert addr == 1, f"PC should advance to 1, got {addr}"


@cocotb.test()
async def test_add(dut):
    """LDI r0, 3 ; LDI r1, 5 ; ADD r2, r0, r1."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 0, 3), expected_pc=0)
    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 1, 5), expected_pc=1)
    await do_fetch_cycle(dut, enc_r(OP_ADD, 2, 0, 1), expected_pc=2)

    await wait_cs_low(dut)
    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_IFETCH
    await inter_byte_gap(dut)
    addr = await spi_clock_byte(dut)
    assert addr == 3, f"PC should be 3, got {addr}"


@cocotb.test()
async def test_jmp(dut):
    """JMP 0x10 — verify PC jumps."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    await do_fetch_cycle(dut, enc_imm8(OP_JMP, 0, 0x10), expected_pc=0)

    await wait_cs_low(dut)
    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_IFETCH
    await inter_byte_gap(dut)
    addr = await spi_clock_byte(dut)
    assert addr == 0x10, f"PC should jump to 0x10, got {addr:#04x}"


@cocotb.test()
async def test_load(dut):
    """LOAD r0, [r1 + 2] — verify SPI FAST_READ protocol."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 1, 0x30), expected_pc=0)

    load_instr = enc_imm6(OP_LOAD, 0, 1, 2)
    await do_fetch_cycle(dut, load_instr, expected_pc=1)

    # FAST_READ transaction
    await wait_cs_low(dut)

    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_LOAD, f"expected 0x0B, got {cmd:#04x}"
    await inter_byte_gap(dut)

    addr = await spi_clock_byte(dut)
    assert addr == 0x32, f"expected addr 0x32, got {addr:#04x}"
    await inter_byte_gap(dut)

    await spi_clock_byte(dut)  # DUMMY
    await inter_byte_gap(dut)

    await spi_clock_byte(dut, 0xAB)  # data response
    await wait_cs_high(dut)

    # Next fetch at PC=2
    await wait_cs_low(dut)
    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_IFETCH
    await inter_byte_gap(dut)
    addr = await spi_clock_byte(dut)
    assert addr == 2, f"PC should be 2, got {addr}"


@cocotb.test()
async def test_store(dut):
    """STORE [r1 + 4], r0 — verify WREN + WRITE protocol."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 0, 0x55), expected_pc=0)
    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 1, 0x20), expected_pc=1)

    store_instr = enc_imm6(OP_STORE, 0, 1, (0 << 3) | 4)
    await do_fetch_cycle(dut, store_instr, expected_pc=2)

    # WREN CS cycle
    await wait_cs_low(dut)
    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_WREN, f"expected WREN 0x06, got {cmd:#04x}"
    await wait_cs_high(dut)

    # WRITE CS cycle
    await wait_cs_low(dut)
    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_STORE, f"expected WRITE 0x02, got {cmd:#04x}"
    await inter_byte_gap(dut)

    addr = await spi_clock_byte(dut)
    assert addr == 0x24, f"expected addr 0x24, got {addr:#04x}"
    await inter_byte_gap(dut)

    data = await spi_clock_byte(dut)
    assert data == 0x55, f"expected data 0x55, got {data:#04x}"
    await wait_cs_high(dut)

    # Next fetch at PC=3
    await wait_cs_low(dut)
    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_IFETCH
    await inter_byte_gap(dut)
    addr = await spi_clock_byte(dut)
    assert addr == 3, f"PC should be 3, got {addr}"


OP_BEZ = 0xC


@cocotb.test()
async def test_bez_taken(dut):
    """BEZ branches when rs1 == 0."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    # LDI r0, 0 (zero — BEZ should branch)
    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 0, 0), expected_pc=0)

    # BEZ r0, 0x10
    await do_fetch_cycle(dut, enc_imm8(OP_BEZ, 0, 0x10), expected_pc=1)

    # Next fetch should be at PC=0x10 (branch taken)
    await wait_cs_low(dut)
    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_IFETCH
    await inter_byte_gap(dut)
    addr = await spi_clock_byte(dut)
    assert addr == 0x10, f"PC should jump to 0x10 after BEZ (r0==0), got {addr:#04x}"


@cocotb.test()
async def test_bez_not_taken(dut):
    """BEZ does not branch when rs1 != 0."""
    cocotb.start_soon(Clock(dut.clk, SYS_CLK_PERIOD, units="ns").start())
    await reset(dut)

    # LDI r0, 42 (non-zero — BEZ should NOT branch)
    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 0, 42), expected_pc=0)

    # BEZ r0, 0x10
    await do_fetch_cycle(dut, enc_imm8(OP_BEZ, 0, 0x10), expected_pc=1)

    # Next fetch should be at PC=2 (fall through, not taken)
    await wait_cs_low(dut)
    cmd = await spi_clock_byte(dut)
    assert cmd == CMD_IFETCH
    await inter_byte_gap(dut)
    addr = await spi_clock_byte(dut)
    assert addr == 2, f"PC should be 2 (fall through, r0!=0), got {addr:#04x}"
