`default_nettype none
`timescale 1ns / 1ps

module tb_pipeline_reg ();

  initial begin
    $dumpvars(0, tb_pipeline_reg);
    #1;
  end

  reg [7:0] D;
  reg latch, clk, rst_n;
  wire [7:0] Q;

  pipeline_reg #(.N(8)) dut (
    .o_Q(Q),
    .i_D(D),
    .i_latch(latch),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
