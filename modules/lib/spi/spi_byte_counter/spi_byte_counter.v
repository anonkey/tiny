`default_nettype none

// SPI byte counter — counts 8 SCLK edges per byte.
// Resets when CS deasserted or when count reaches 8.
// Pulses o_byte_done for one clock when a complete byte is received.
// Latches the RX shift register contents into o_rx_data on byte_done.

module spi_byte_counter (
  output wire       o_byte_done,
  output wire [7:0] o_rx_data,
  input  wire [7:0] i_rx_shift,
  input  wire       i_sclk_rise,
  input  wire       i_cs_n,
  input  wire       i_clk,
  input  wire       i_rst_n
);

  // 4-bit counter: reset on CS deassert or byte complete, increment on SCLK rise
  wire [3:0] w_cnt;
  wire       w_byte_complete = (w_cnt == 4'd8);
  wire       w_cnt_en   = i_cs_n | i_sclk_rise | w_byte_complete;
  wire [3:0] w_cnt_next = (i_cs_n | w_byte_complete) ? 4'd0
                                                      : (w_cnt + 4'd1);

  register #(.N(4)) cnt_reg (
    .o_Q(w_cnt),
    .i_D(w_cnt_next),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(w_cnt_en)
  );

  // RX output latch: capture shift register on byte complete
  register #(.N(8)) rx_latch (
    .o_Q(o_rx_data),
    .i_D(i_rx_shift),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(w_byte_complete)
  );

  // byte_done pulse: registered version of byte_complete
  dff done_ff (
    .o_Q(o_byte_done), .o_Qn(),
    .i_D(w_byte_complete),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

endmodule
