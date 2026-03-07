`default_nettype none
`timescale 1ns / 1ps

module tb_dff ();

  initial begin
    $dumpfile("tb_dff.fst");
    $dumpvars(0, tb_dff);
    #1;
  end

  reg D, clk, rst_n, en;
  wire Q, Qn;

  dff dut (
    .Q(Q),
    .Qn(Qn),
    .D(D),
    .clk(clk),
    .rst_n(rst_n),
    .en(en)
  );

endmodule
