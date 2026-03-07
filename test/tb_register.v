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
    .Q(Q),
    .D(D),
    .clk(clk),
    .rst_n(rst_n),
    .en(en)
  );

endmodule
