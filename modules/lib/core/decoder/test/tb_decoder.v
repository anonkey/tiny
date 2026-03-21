`default_nettype none
`timescale 1ns / 1ps

module tb_decoder ();

  initial begin
    $dumpvars(0, tb_decoder);
    #1;
  end

  reg [15:0] instr;
  wire [3:0] alu_op;
  wire [2:0] rd, rs1, rs2;
  wire [7:0] imm8;
  wire [5:0] imm6;
  wire reg_we, alu_src, pc_load, use_imm8;

  decoder dut (
    .o_alu_op(alu_op),
    .o_rd(rd),
    .o_rs1(rs1),
    .o_rs2(rs2),
    .o_imm8(imm8),
    .o_imm6(imm6),
    .o_reg_we(reg_we),
    .o_alu_src(alu_src),
    .o_pc_load(pc_load),
    .o_use_imm8(use_imm8),
    .i_instr(instr)
  );

endmodule
