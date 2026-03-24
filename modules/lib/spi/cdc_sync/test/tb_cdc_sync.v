`default_nettype none
`timescale 1ns / 1ps

module tb_cdc_sync ();

  initial begin
    $dumpvars(0, tb_cdc_sync);
    #1;
  end

  reg  async_in, clk, rst_n;
  wire sync, rise, fall;

  cdc_sync #(.STAGES(2)) dut_sync (
    .o_sync(sync),
    .i_async(async_in),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

  edge_detect dut_edge (
    .o_rise(rise),
    .o_fall(fall),
    .i_sync(sync),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
