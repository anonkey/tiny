`default_nettype none
`timescale 1ns / 1ps

module tb_cpu ();

  initial begin
    $dumpfile("../artifacts/tb_cpu.fst");
    $dumpvars(0, tb_cpu);
    #1;
  end

  reg clk, rst_n;
  wire [7:0] pc_out, alu_out;
  wire [15:0] instr_out;

  cpu dut (
    .o_pc(pc_out),
    .o_instr(instr_out),
    .o_alu(alu_out),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
