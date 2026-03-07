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
    .pc_out(pc_out),
    .load_addr(load_addr),
    .load(load),
    .clk(clk),
    .rst_n(rst_n)
  );

endmodule
