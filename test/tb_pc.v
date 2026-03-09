`default_nettype none
`timescale 1ns / 1ps

module tb_pc ();

  initial begin
    $dumpfile("tb_pc.fst");
    $dumpvars(0, tb_pc);
    #1;
  end

  reg [7:0] load_addr;
  reg load, clk, rst_n;
  wire [7:0] pc_out;

  pc dut (
    .o_pc(pc_out),
    .i_load_addr(load_addr),
    .i_load(load),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
