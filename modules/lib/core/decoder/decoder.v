`default_nettype none

module decoder(
   o_alu_op, o_rd, o_rs1, o_rs2, o_imm8, o_imm6,
   o_reg_we, o_alu_src, o_pc_load, o_use_imm8,
   o_is_load, o_is_store, o_is_beq,
   i_instr
);

   output [3:0] o_alu_op;
   output [2:0] o_rd;
   output [2:0] o_rs1;
   output [2:0] o_rs2;
   output [7:0] o_imm8;
   output [5:0] o_imm6;
   output       o_reg_we;
   output       o_alu_src;    // 0 = rs2, 1 = imm6
   output       o_pc_load;
   output       o_use_imm8;   // 1 = write imm8 to rd (LDI)
   output       o_is_load;    // LOAD  (1101)
   output       o_is_store;   // STORE (1110)
   output       o_is_beq;     // BEQ   (1100)

   input [15:0] i_instr;

   wire [3:0] w_opcode;

   // Field extraction
   assign w_opcode = i_instr[15:12];
   assign o_rd     = i_instr[11:9];
   assign o_rs1    = i_instr[8:6];
   assign o_rs2    = i_instr[5:3];
   assign o_imm6   = i_instr[5:0];
   assign o_imm8   = i_instr[8:1];

   // Instruction type flags
   assign o_is_load  = w_opcode[3] & w_opcode[2] & ~w_opcode[1] & w_opcode[0];  // 1101
   assign o_is_store = w_opcode[3] & w_opcode[2] & w_opcode[1] & ~w_opcode[0];  // 1110
   assign o_is_beq   = w_opcode[3] & w_opcode[2] & ~w_opcode[1] & ~w_opcode[0]; // 1100

   // ALU opcode: passthrough for R-type (0000-0101).
   // ADDI (1001), LOAD (1101), STORE (1110) → force ADD (0000).
   // All others pass through (unused slots produce 0 in ALU mux).
   wire w_force_add;
   assign w_force_add = w_opcode[3] & (
                        (~w_opcode[2] & ~w_opcode[1] & w_opcode[0]) |  // 1001 ADDI
                        (w_opcode[2] & ~w_opcode[1] & w_opcode[0]) |   // 1101 LOAD
                        (w_opcode[2] & w_opcode[1] & ~w_opcode[0])     // 1110 STORE
                      );
   assign o_alu_op = w_force_add ? 4'b0000 : w_opcode;

   // reg_we: write to register file for all ops except JMP (1011),
   // BEQ (1100), STORE (1110), NOP (1111)
   assign o_reg_we = ~w_opcode[3] |                                          // 0000-0111
                   (w_opcode[3] & ~w_opcode[2] & ~w_opcode[1] & w_opcode[0]) |   // 1001 ADDI
                   (w_opcode[3] & ~w_opcode[2] & w_opcode[1] & ~w_opcode[0]) |   // 1010 LDI
                   (w_opcode[3] & w_opcode[2] & ~w_opcode[1] & w_opcode[0]);     // 1101 LOAD

   // alu_src: use imm6 instead of rs2 for ADDI (1001), LOAD (1101), STORE (1110)
   assign o_alu_src = w_opcode[3] & (
                     (~w_opcode[2] & ~w_opcode[1] & w_opcode[0]) |  // 1001
                     (w_opcode[2] & ~w_opcode[1] & w_opcode[0]) |   // 1101
                     (w_opcode[2] & w_opcode[1] & ~w_opcode[0])     // 1110
                   );

   // pc_load: jump for JMP (1011), BEQ handled externally with zero flag
   assign o_pc_load = w_opcode[3] & ~w_opcode[2] & w_opcode[1] & w_opcode[0]; // 1011

   // use_imm8: LDI (1010) loads 8-bit immediate directly into rd
   assign o_use_imm8 = w_opcode[3] & ~w_opcode[2] & w_opcode[1] & ~w_opcode[0]; // 1010

endmodule
