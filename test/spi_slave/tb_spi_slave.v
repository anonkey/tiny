`default_nettype none
`timescale 1ns / 1ps

module tb_spi_slave ();

  initial begin
    $dumpfile("../artifacts/tb_spi_slave.fst");
    $dumpvars(0, tb_spi_slave);
    #1;
  end

  reg         clk, rst_n;
  reg         sclk, mosi, cs_n;
  reg  [15:0] tx_data;
  reg         tx_load;
  wire [15:0] rx_data;
  wire        rx_done;
  wire        miso;

  spi_slave dut (
    .o_rx_data(rx_data),
    .o_rx_done(rx_done),
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
