`default_nettype none
`timescale 1ns / 1ps

module tb_regfile ();

  initial begin
    $dumpfile("tb_regfile.fst");
    $dumpvars(0, tb_regfile);
    #1;
  end

  reg [7:0] wd;
  reg [2:0] raddr1, raddr2, waddr;
  reg we, clk, rst_n;
  wire [7:0] rd1, rd2;

  regfile dut (
    .o_rd1(rd1),
    .o_rd2(rd2),
    .i_wd(wd),
    .i_raddr1(raddr1),
    .i_raddr2(raddr2),
    .i_waddr(waddr),
    .i_we(we),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
