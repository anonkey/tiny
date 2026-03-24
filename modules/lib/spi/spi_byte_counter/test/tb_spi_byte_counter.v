`default_nettype none
`timescale 1ns / 1ps

module tb_spi_byte_counter ();

  initial begin
    $dumpvars(0, tb_spi_byte_counter);
    #1;
  end

  reg         clk = 0;
  reg         rst_n = 0;
  reg         sclk_rise = 0;
  reg         cs_n = 1;
  reg  [7:0]  rx_shift = 0;

  wire        byte_done;
  wire [7:0]  rx_data;

  spi_byte_counter #(.BYTE_WIDTH(8)) dut (
    .o_byte_done(byte_done),
    .o_rx_data(rx_data),
    .i_rx_shift(rx_shift),
    .i_sclk_rise(sclk_rise),
    .i_cs_n(cs_n),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
