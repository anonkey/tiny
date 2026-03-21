`default_nettype none
`timescale 1ns / 1ps

module tb_dff ();

  initial begin
    $dumpfile("../artifacts/tb_dff.fst");
    $dumpvars(0, tb_dff);
    #1;
  end

  reg D, clk, rst_n, en;
  wire Q, Qn;

  dff dut (
    .o_Q(Q),
    .o_Qn(Qn),
    .i_D(D),
    .i_clk(clk),
    .i_rst_n(rst_n),
    .i_en(en)
  );

endmodule
