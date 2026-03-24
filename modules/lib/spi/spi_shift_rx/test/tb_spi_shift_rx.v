`default_nettype none
`timescale 1ns / 1ps

module tb_spi_shift_rx ();

  initial begin
    $dumpvars(0, tb_spi_shift_rx);
    #1;
  end

  reg  clk = 0;
  reg  rst_n = 0;
  reg  bit_in = 0;
  reg  shift_en = 0;

  wire [7:0] data;

  spi_shift_rx dut (
    .o_data(data),
    .i_bit(bit_in),
    .i_shift_en(shift_en),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
