import cocotb
from cocotb.triggers import Timer


def build_r_type(opcode, rd, rs1, rs2):
    return (opcode << 12) | (rd << 9) | (rs1 << 6) | (rs2 << 3)


def build_i_type(opcode, rd, rs1, imm6):
    return (opcode << 12) | (rd << 9) | (rs1 << 6) | (imm6 & 0x3F)


def build_l_type(opcode, rd, imm8):
    return (opcode << 12) | (rd << 9) | ((imm8 & 0xFF) << 1)


@cocotb.test()
async def test_field_extraction_r_type(dut):
    """R-type fields: opcode, rd, rs1, rs2 extracted correctly."""
    instr = build_r_type(0b0000, 0b101, 0b011, 0b110)
    dut.instr.value = instr
    await Timer(1, units="ns")

    assert int(dut.alu_op.value) == 0b0000, f"alu_op: {int(dut.alu_op.value):#06b}"
    assert int(dut.rd.value) == 0b101, f"rd: {int(dut.rd.value):#05b}"
    assert int(dut.rs1.value) == 0b011, f"rs1: {int(dut.rs1.value):#05b}"
    assert int(dut.rs2.value) == 0b110, f"rs2: {int(dut.rs2.value):#05b}"


@cocotb.test()
async def test_field_extraction_i_type(dut):
    """I-type fields: opcode, rd, rs1, imm6 extracted correctly."""
    instr = build_i_type(0b1001, 0b010, 0b100, 0b101010)
    dut.instr.value = instr
    await Timer(1, units="ns")

    assert int(dut.alu_op.value) == 0b0000, "ADDI should map alu_op to ADD (0000)"
    assert int(dut.rd.value) == 0b010
    assert int(dut.rs1.value) == 0b100
    assert int(dut.imm6.value) == 0b101010


@cocotb.test()
async def test_field_extraction_l_type(dut):
    """L-type fields: opcode, rd, imm8 extracted correctly."""
    instr = build_l_type(0b1010, 0b111, 0xA5)
    dut.instr.value = instr
    await Timer(1, units="ns")

    assert int(dut.alu_op.value) == 0b1010, "LDI passes opcode through (not ADD/STORE)"
    assert int(dut.rd.value) == 0b111
    assert int(dut.imm8.value) == 0xA5


@cocotb.test()
async def test_reg_we_r_type(dut):
    """R-type ALU ops (0000-0101) should assert reg_we."""
    for opcode in range(6):  # ADD through NOT
        instr = build_r_type(opcode, 1, 2, 3)
        dut.instr.value = instr
        await Timer(1, units="ns")
        assert int(dut.reg_we.value) == 1, (
            f"opcode {opcode:#06b}: reg_we should be 1"
        )


@cocotb.test()
async def test_reg_we_addi_ldi_load(dut):
    """ADDI (1001), LDI (1010), LOAD (1101) should assert reg_we."""
    for opcode in [0b1001, 0b1010, 0b1101]:
        dut.instr.value = opcode << 12
        await Timer(1, units="ns")
        assert int(dut.reg_we.value) == 1, (
            f"opcode {opcode:#06b}: reg_we should be 1"
        )


@cocotb.test()
async def test_reg_we_off(dut):
    """Unused (0110-0111), reserved (1000), JMP (1011), BEZ (1100), STORE (1110), NOP (1111) should deassert reg_we."""
    for opcode in [0b0110, 0b0111, 0b1000, 0b1011, 0b1100, 0b1110, 0b1111]:
        dut.instr.value = opcode << 12
        await Timer(1, units="ns")
        assert int(dut.reg_we.value) == 0, (
            f"opcode {opcode:#06b}: reg_we should be 0"
        )


@cocotb.test()
async def test_alu_src_immediate(dut):
    """ADDI (1001), LOAD (1101), STORE (1110) should assert alu_src."""
    for opcode in [0b1001, 0b1101, 0b1110]:
        dut.instr.value = opcode << 12
        await Timer(1, units="ns")
        assert int(dut.alu_src.value) == 1, (
            f"opcode {opcode:#06b}: alu_src should be 1"
        )


@cocotb.test()
async def test_alu_src_register(dut):
    """R-type ops should deassert alu_src (use rs2)."""
    for opcode in range(6):
        dut.instr.value = opcode << 12
        await Timer(1, units="ns")
        assert int(dut.alu_src.value) == 0, (
            f"opcode {opcode:#06b}: alu_src should be 0"
        )


@cocotb.test()
async def test_pc_load(dut):
    """Only JMP (1011) should assert pc_load."""
    for opcode in range(16):
        dut.instr.value = opcode << 12
        await Timer(1, units="ns")
        expected = 1 if opcode == 0b1011 else 0
        assert int(dut.pc_load.value) == expected, (
            f"opcode {opcode:#06b}: pc_load should be {expected}, got {int(dut.pc_load.value)}"
        )


@cocotb.test()
async def test_use_imm8(dut):
    """Only LDI (1010) should assert use_imm8."""
    for opcode in range(16):
        dut.instr.value = opcode << 12
        await Timer(1, units="ns")
        expected = 1 if opcode == 0b1010 else 0
        assert int(dut.use_imm8.value) == expected, (
            f"opcode {opcode:#06b}: use_imm8 should be {expected}, got {int(dut.use_imm8.value)}"
        )


@cocotb.test()
async def test_bez_fields(dut):
    """BEZ (1100) should: extract rs1 from rd slot [11:9], force alu_op to ADD, assert is_beq."""
    # BEZ r5, 0x42 → opcode=1100, rs1(rd slot)=101, imm8=0x42
    instr = build_l_type(0b1100, 0b101, 0x42)
    dut.instr.value = instr
    await Timer(1, units="ns")

    assert int(dut.is_beq.value) == 1, "is_beq should be asserted"
    assert int(dut.rs1.value) == 0b101, f"rs1 should be 5 (from rd slot), got {int(dut.rs1.value)}"
    assert int(dut.imm8.value) == 0x42, f"imm8 should be 0x42, got {int(dut.imm8.value):#x}"
    assert int(dut.alu_op.value) == 0b0000, f"alu_op should be ADD (0000), got {int(dut.alu_op.value):#06b}"
    assert int(dut.reg_we.value) == 0, "reg_we should be 0 for BEZ"
    assert int(dut.pc_load.value) == 0, "pc_load should be 0 for BEZ (handled by zero flag)"


@cocotb.test()
async def test_all_fields_all_opcodes(dut):
    """Sweep all 16 opcodes with distinct field values, verify extraction."""
    for opcode in range(16):
        rd_val = opcode % 8
        rs1_val = (opcode + 1) % 8
        rs2_val = (opcode + 2) % 8
        instr = build_r_type(opcode, rd_val, rs1_val, rs2_val)
        dut.instr.value = instr
        await Timer(1, units="ns")

        # ADDI(1001), BEZ(1100), LOAD(1101), STORE(1110) map alu_op to ADD(0000)
        if opcode in (0b1001, 0b1100, 0b1101, 0b1110):
            expected_alu = 0b0000
        else:
            expected_alu = opcode
        assert int(dut.alu_op.value) == expected_alu, (
            f"alu_op mismatch at opcode {opcode:#06b}: "
            f"expected {expected_alu:#06b}, got {int(dut.alu_op.value):#06b}"
        )
        assert int(dut.rd.value) == rd_val, f"rd mismatch at opcode {opcode}"
        # BEZ reads rs1 from rd slot [11:9]
        if opcode == 0b1100:
            assert int(dut.rs1.value) == rd_val, f"BEZ rs1 mismatch (should be rd slot)"
        else:
            assert int(dut.rs1.value) == rs1_val, f"rs1 mismatch at opcode {opcode}"
        assert int(dut.rs2.value) == rs2_val, f"rs2 mismatch at opcode {opcode}"
