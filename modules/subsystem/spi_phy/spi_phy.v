`default_nettype none

// SPI PHY — 8-bit byte-oriented half-duplex protocol (structural)
//
// Shifts 8 bits per byte. Pulses o_byte_done after every 8 SCLK rising
// edges while CS is active. CS_n is driven synchronously by mem_ctrl
// (no internal CS synchronizer needed).
//
// TX: load i_tx_data via i_tx_load, shifts out MSB-first on SCLK falling edge.
// RX: shifts in MOSI on SCLK rising edge, latches o_rx_data on byte_done.

module spi_phy (
  // RX: data received from master
  output wire [7:0]  o_rx_data,
  output wire        o_byte_done,

  // TX: data to send (drives MISO shift register)
  input  wire [7:0]  i_tx_data,
  input  wire        i_tx_load,  // pulse to load tx shift register

  // MISO output
  output wire        o_miso,

  // SPI bus
  input  wire        i_sclk,
  input  wire        i_mosi,
  input  wire        i_cs_n,     // synchronous (driven by mem_ctrl)

  // System
  input  wire        i_clk,
  input  wire        i_rst_n
);

  // =====================================================================
  // Synchronize SCLK into system clock domain (3-stage) + edge detect
  // =====================================================================
  wire w_sclk_sync;

  cdc_sync #(.STAGES(3)) sclk_cdc (
    .o_sync(w_sclk_sync),
    .i_async(i_sclk),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  wire w_sclk_rise, w_sclk_fall;

  edge_detect sclk_edge (
    .o_rise(w_sclk_rise),
    .o_fall(w_sclk_fall),
    .i_sync(w_sclk_sync),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  // =====================================================================
  // Synchronize MOSI (2-stage)
  // =====================================================================
  wire w_mosi_sync;

  cdc_sync #(.STAGES(2)) mosi_cdc (
    .o_sync(w_mosi_sync),
    .i_async(i_mosi),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  // =====================================================================
  // TX shift register (MISO)
  // =====================================================================
  wire w_tx_shift_en = ~i_cs_n & w_sclk_fall;

  spi_shift_tx tx (
    .o_miso(o_miso),
    .i_data(i_tx_data),
    .i_load(i_tx_load),
    .i_shift_en(w_tx_shift_en),
    .i_active(~i_cs_n),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  // =====================================================================
  // RX shift register (MOSI)
  // =====================================================================
  wire [7:0] w_rx_shift;
  wire       w_rx_en = ~i_cs_n & w_sclk_rise;

  spi_shift_rx rx (
    .o_data(w_rx_shift),
    .i_bit(w_mosi_sync),
    .i_shift_en(w_rx_en),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  // =====================================================================
  // Byte counter + RX latch + byte_done pulse
  // =====================================================================
  spi_byte_counter byte_cnt (
    .o_byte_done(o_byte_done),
    .o_rx_data(o_rx_data),
    .i_rx_shift(w_rx_shift),
    .i_sclk_rise(w_sclk_rise),
    .i_cs_n(i_cs_n),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

endmodule
