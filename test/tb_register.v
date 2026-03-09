`default_nettype none
`timescale 1ns / 1ps

module tb_register ();

  initial begin
    $dumpfile("tb_register.fst");
    $dumpvars(0, tb_register);
    #1;
  end

  reg [7:0] D;
  reg clk, rst_n, en;
  wire [7:0] Q;

  register #(.N(8)) dut (
    .o_Q(Q),
    .i_D(D),
    .i_clk(clk),
    .i_rst_n(rst_n),
    .i_en(en)
  );

endmodule
