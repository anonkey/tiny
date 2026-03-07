module decoder(
   alu_op, rd, rs1, rs2, imm8, imm6,
   reg_we, alu_src, pc_load, use_imm8,
   instr
);

   output [3:0] alu_op;
   output [2:0] rd;
   output [2:0] rs1;
   output [2:0] rs2;
   output [7:0] imm8;
   output [5:0] imm6;
   output       reg_we;
   output       alu_src;   // 0 = rs2, 1 = imm6
   output       pc_load;
   output       use_imm8;  // 1 = write imm8 to rd (LDI)

   input [15:0] instr;

   wire [3:0] opcode;

   // Field extraction
   assign opcode = instr[15:12];
   assign rd     = instr[11:9];
   assign rs1    = instr[8:6];
   assign rs2    = instr[5:3];
   assign imm6   = instr[5:0];
   assign imm8   = instr[8:1];

   // ALU opcode: passthrough for R-type (0000-1000).
   // ADDI (1001) → force ADD (0000), LOAD/STORE (1101/1110) → force ADD (0000).
   // All others pass through (unused slots produce 0 in ALU mux).
   wire addi_or_mem;
   assign addi_or_mem = opcode[3] & (
                          (~opcode[2] & ~opcode[1] & opcode[0]) |  // 1001 ADDI
                          (opcode[2] & ~opcode[1] & opcode[0]) |   // 1101 LOAD
                          (opcode[2] & opcode[1] & ~opcode[0])     // 1110 STORE
                        );
   assign alu_op = {opcode[3] & ~addi_or_mem, opcode[2] & ~addi_or_mem,
                    opcode[1] & ~addi_or_mem, opcode[0] & ~addi_or_mem};

   // reg_we: write to register file for all ops except JMP (1011),
   // BEQ (1100), STORE (1110), NOP (1111)
   // R-type: 0000-1000, ADDI: 1001, LDI: 1010, LOAD: 1101
   assign reg_we = ~opcode[3] |                                          // 0000-0111
                   (opcode[3] & ~opcode[2] & ~opcode[1] & ~opcode[0]) |  // 1000 XNOR
                   (opcode[3] & ~opcode[2] & ~opcode[1] & opcode[0]) |   // 1001 ADDI
                   (opcode[3] & ~opcode[2] & opcode[1] & ~opcode[0]) |   // 1010 LDI
                   (opcode[3] & opcode[2] & ~opcode[1] & opcode[0]);     // 1101 LOAD

   // alu_src: use imm6 instead of rs2 for ADDI (1001), LOAD (1101), STORE (1110)
   assign alu_src = opcode[3] & (
                      (~opcode[2] & ~opcode[1] & opcode[0]) |  // 1001
                      (opcode[2] & ~opcode[1] & opcode[0]) |   // 1101
                      (opcode[2] & opcode[1] & ~opcode[0])     // 1110
                    );

   // pc_load: jump for JMP (1011), BEQ handled externally with zero flag
   assign pc_load = opcode[3] & ~opcode[2] & opcode[1] & opcode[0]; // 1011

   // use_imm8: LDI (1010) loads 8-bit immediate directly into rd
   assign use_imm8 = opcode[3] & ~opcode[2] & opcode[1] & ~opcode[0]; // 1010

endmodule
