`default_nettype none
`timescale 1ns / 1ps

module tb_decoder ();

  initial begin
    $dumpfile("tb_decoder.fst");
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
    .alu_op(alu_op),
    .rd(rd),
    .rs1(rs1),
    .rs2(rs2),
    .imm8(imm8),
    .imm6(imm6),
    .reg_we(reg_we),
    .alu_src(alu_src),
    .pc_load(pc_load),
    .use_imm8(use_imm8),
    .instr(instr)
  );

endmodule
