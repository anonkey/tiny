`default_nettype none
`timescale 1ns / 1ps

module tb_read_data_accum ();

  initial begin
    $dumpvars(0, tb_read_data_accum);
    #1;
  end

  reg [7:0] rx_byte;
  reg latch_hi, latch_lo;
  reg clk, rst_n;
  wire [15:0] read_data;

  read_data_accum dut (
    .o_read_data(read_data),
    .i_rx_byte(rx_byte),
    .i_latch_hi(latch_hi),
    .i_latch_lo(latch_lo),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
