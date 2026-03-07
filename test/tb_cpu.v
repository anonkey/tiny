`default_nettype none
`timescale 1ns / 1ps

module tb_cpu ();

  initial begin
    $dumpfile("tb_cpu.fst");
    $dumpvars(0, tb_cpu);
    #1;
  end

  reg clk, rst_n;
  wire [7:0] pc_out, alu_out;
  wire [15:0] instr_out;

  cpu dut (
    .pc_out(pc_out),
    .instr_out(instr_out),
    .alu_out(alu_out),
    .clk(clk),
    .rst_n(rst_n)
  );

endmodule
