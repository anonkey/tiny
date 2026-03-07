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
    .rd1(rd1),
    .rd2(rd2),
    .wd(wd),
    .raddr1(raddr1),
    .raddr2(raddr2),
    .waddr(waddr),
    .we(we),
    .clk(clk),
    .rst_n(rst_n)
  );

endmodule
