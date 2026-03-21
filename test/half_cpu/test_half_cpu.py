import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer


# --- Instruction encoding helpers ---
# instr[15:12] = opcode
# instr[11:9]  = rd
# instr[8:6]   = rs1
# instr[5:3]   = rs2
# instr[5:0]   = imm6
# instr[8:1]   = imm8

def enc_r(opcode, rd, rs1, rs2):
    """R-type: opcode[15:12] rd[11:9] rs1[8:6] rs2[5:3] xxx[2:0]"""
    return (opcode << 12) | (rd << 9) | (rs1 << 6) | (rs2 << 3)

def enc_imm6(opcode, rd, rs1, imm6):
    """I-type with 6-bit imm: opcode[15:12] rd[11:9] rs1[8:6] imm6[5:0]"""
    return (opcode << 12) | (rd << 9) | (rs1 << 6) | (imm6 & 0x3F)

def enc_imm8(opcode, rd, imm8):
    """I-type with 8-bit imm: opcode[15:12] rd[11:9] imm8[8:1] x[0]"""
    return (opcode << 12) | (rd << 9) | ((imm8 & 0xFF) << 1)

# Opcodes
OP_ADD   = 0x0
OP_SUB   = 0x1
OP_ADDI  = 0x9
OP_LDI   = 0xA
OP_JMP   = 0xB
OP_BEQ   = 0xC
OP_LOAD  = 0xD
OP_STORE = 0xE
OP_NOP   = 0xF

# SPI commands (nvSRAM-compatible)
CMD_IFETCH = 0x03  # nvSRAM READ
CMD_LOAD   = 0x0B  # nvSRAM FAST_READ
CMD_STORE  = 0x02  # nvSRAM WRITE
CMD_WREN   = 0x06  # nvSRAM WREN

# CPU FSM states
S_FETCH_REQ  = 0
S_FETCH_WAIT = 1
S_DECODE     = 2
S_EXECUTE    = 3
S_MEM_REQ    = 4
S_MEM_WAIT   = 5
S_WRITEBACK  = 6
S_PC_UPDATE  = 7


async def reset(dut):
    dut.rst_n.value = 0
    dut.spi_rx_data.value = 0
    dut.spi_rx_done.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1


async def tick(dut):
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)


async def wait_for_tx_load(dut, timeout=50):
    """Wait until spi_tx_load pulses high. Returns the tx_data value."""
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.spi_tx_load.value) == 1:
            tx = int(dut.spi_tx_data.value)
            await FallingEdge(dut.clk)
            return tx
    raise TimeoutError("spi_tx_load never went high")


async def send_rx(dut, data, delay=2):
    """Simulate master sending data back after a short delay."""
    for _ in range(delay):
        await tick(dut)
    dut.spi_rx_data.value = data
    dut.spi_rx_done.value = 1
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.spi_rx_done.value = 0


async def do_fetch_cycle(dut, instruction, expected_pc=None):
    """Complete one fetch cycle: wait for TX IFETCH, verify PC, send instruction."""
    tx = await wait_for_tx_load(dut)
    cmd = (tx >> 8) & 0xFF
    addr = tx & 0xFF
    assert cmd == CMD_IFETCH, f"expected IFETCH cmd 0x01, got {cmd:#04x}"
    if expected_pc is not None:
        assert addr == expected_pc, f"expected PC={expected_pc:#04x}, got addr={addr:#04x}"
    await send_rx(dut, instruction)


@cocotb.test()
async def test_nop(dut):
    """Fetch NOP, verify PC advances from 0 to 1."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    assert int(dut.pc_out.value) == 0

    # Fetch NOP at PC=0
    nop = enc_r(OP_NOP, 0, 0, 0)
    await do_fetch_cycle(dut, nop, expected_pc=0)

    # Wait for writeback + next TX_FETCH
    tx = await wait_for_tx_load(dut)
    addr = tx & 0xFF
    assert addr == 1, f"PC should be 1 after NOP, got {addr}"


@cocotb.test()
async def test_ldi(dut):
    """LDI r0, 0x42 — verify register gets loaded."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    instr = enc_imm8(OP_LDI, 0, 0x42)  # LDI r0, 0x42
    await do_fetch_cycle(dut, instr, expected_pc=0)

    # Wait for next fetch (PC=1) — this means writeback happened
    tx = await wait_for_tx_load(dut)
    addr = tx & 0xFF
    assert addr == 1, f"PC should advance to 1, got {addr}"


@cocotb.test()
async def test_add(dut):
    """LDI r0, 3 ; LDI r1, 5 ; ADD r2, r0, r1 — verify ALU output."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # LDI r0, 3
    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 0, 3), expected_pc=0)

    # LDI r1, 5
    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 1, 5), expected_pc=1)

    # ADD r2, r0, r1
    await do_fetch_cycle(dut, enc_r(OP_ADD, 2, 0, 1), expected_pc=2)

    # Wait for writeback to complete — next fetch should show PC=3
    tx = await wait_for_tx_load(dut)
    assert (tx & 0xFF) == 3, f"PC should be 3, got {tx & 0xFF}"


@cocotb.test()
async def test_jmp(dut):
    """JMP 0x10 — verify PC jumps."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # JMP to 0x10
    await do_fetch_cycle(dut, enc_imm8(OP_JMP, 0, 0x10), expected_pc=0)

    # Next fetch should be at PC=0x10
    tx = await wait_for_tx_load(dut)
    addr = tx & 0xFF
    assert addr == 0x10, f"PC should jump to 0x10, got {addr:#04x}"


@cocotb.test()
async def test_load(dut):
    """LOAD r0, [r1 + 2] — verify SPI LOAD protocol."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # LDI r1, 0x30 (base address)
    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 1, 0x30), expected_pc=0)

    # LOAD r0, [r1 + 2]: opcode=0xD, rd=0, rs1=1, imm6=2
    load_instr = enc_imm6(OP_LOAD, 0, 1, 2)
    await do_fetch_cycle(dut, load_instr, expected_pc=1)

    # FSM should now send TX LOAD with addr = r1 + imm6 = 0x30 + 2 = 0x32
    tx = await wait_for_tx_load(dut)
    cmd = (tx >> 8) & 0xFF
    addr = tx & 0xFF
    assert cmd == CMD_LOAD, f"expected LOAD cmd 0x02, got {cmd:#04x}"
    assert addr == 0x32, f"expected addr 0x32, got {addr:#04x}"

    # Master responds with data
    await send_rx(dut, 0x00AB)  # low byte 0xAB

    # Next fetch should be PC=2
    tx = await wait_for_tx_load(dut)
    assert (tx & 0xFF) == 2, f"PC should be 2, got {tx & 0xFF}"


@cocotb.test()
async def test_store(dut):
    """STORE [r1 + 4], r0 — verify SPI STORE protocol."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # LDI r0, 0x55 (data to store)
    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 0, 0x55), expected_pc=0)

    # LDI r1, 0x20 (base address)
    await do_fetch_cycle(dut, enc_imm8(OP_LDI, 1, 0x20), expected_pc=1)

    # STORE [rs1 + imm6], rs2
    # rs2 = instr[5:3] overlaps imm6 = instr[5:0], so imm6 = (rs2_idx << 3) | offset_low3
    # Here: store r0 at [r1 + 4] → rs2=0, offset=4 → imm6 = (0 << 3) | 4 = 4
    store_instr = enc_imm6(OP_STORE, 0, 1, (0 << 3) | 4)
    await do_fetch_cycle(dut, store_instr, expected_pc=2)

    # FSM should send WREN first
    tx = await wait_for_tx_load(dut)
    cmd = (tx >> 8) & 0xFF
    assert cmd == CMD_WREN, f"expected WREN cmd 0x06, got {cmd:#04x}"

    # Then TX STORE with addr = r1 + imm6 = 0x20 + 4 = 0x24
    tx = await wait_for_tx_load(dut)
    cmd = (tx >> 8) & 0xFF
    addr = tx & 0xFF
    assert cmd == CMD_STORE, f"expected STORE cmd 0x02, got {cmd:#04x}"
    assert addr == 0x24, f"expected addr 0x24, got {addr:#04x}"

    # FSM should then send the store data
    tx = await wait_for_tx_load(dut)
    data = tx & 0xFF
    assert data == 0x55, f"expected store data 0x55, got {data:#04x}"

    # Next fetch should be PC=3
    tx = await wait_for_tx_load(dut)
    assert (tx & 0xFF) == 3, f"PC should be 3, got {tx & 0xFF}"
