"""ISA instruction encoding helpers and opcode constants."""

# Opcodes
OP_ADD   = 0b0000
OP_SUB   = 0b0001
OP_AND   = 0b0010
OP_OR    = 0b0011
OP_XOR   = 0b0100
OP_NOT   = 0b0101
OP_ADDI  = 0b1001
OP_LDI   = 0b1010
OP_JMP   = 0b1011
OP_BEZ   = 0b1100
OP_LOAD  = 0b1101
OP_STORE = 0b1110
OP_NOP   = 0b1111


def enc_r(opcode, rd, rs1, rs2):
  """Encode R-type: [opcode:4][rd:3][rs1:3][rs2:3][unused:3]"""
  return (opcode << 12) | (rd << 9) | (rs1 << 6) | (rs2 << 3)


def enc_imm6(opcode, rd, rs1, imm6):
  """Encode I-type: [opcode:4][rd:3][rs1:3][imm6:6]"""
  return (opcode << 12) | (rd << 9) | (rs1 << 6) | (imm6 & 0x3F)


def enc_imm8(opcode, rd, imm8):
  """Encode L-type: [opcode:4][rd:3][imm8:8][0]"""
  return (opcode << 12) | (rd << 9) | ((imm8 & 0xFF) << 1)


def enc_bez(rs1, imm8):
  """Encode BEZ: [1100][rs1:3][imm8:8][0] — rs1 goes in rd slot."""
  return (OP_BEZ << 12) | (rs1 << 9) | ((imm8 & 0xFF) << 1)
