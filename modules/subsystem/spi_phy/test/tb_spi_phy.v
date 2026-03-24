`default_nettype none
`timescale 1ns / 1ps

module tb_spi_phy ();

  initial begin
    $dumpvars(0, tb_spi_phy);
    #1;
  end

  reg        clk, rst_n;
  reg        sclk, mosi, cs_n;
  reg  [7:0] tx_data;
  reg        tx_load;
  wire [7:0] rx_data;
  wire       byte_done;
  wire       miso;

  spi_phy dut (
    .o_rx_data(rx_data),
    .o_byte_done(byte_done),
    .i_tx_data(tx_data),
    .i_tx_load(tx_load),
    .o_miso(miso),
    .i_sclk(sclk),
    .i_mosi(mosi),
    .i_cs_n(cs_n),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
