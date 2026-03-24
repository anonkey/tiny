`default_nettype none

// SPI byte counter — counts BYTE_WIDTH SCLK edges per byte.
// Resets when CS deasserted or when count reaches BYTE_WIDTH.
// Pulses o_byte_done for one clock when a complete byte is received.
// Latches the RX shift register contents into o_rx_data on byte_done.

module spi_byte_counter #(
  parameter BYTE_WIDTH = 8
) (
  output wire                    o_byte_done,
  output wire [BYTE_WIDTH-1:0]  o_rx_data,
  input  wire [BYTE_WIDTH-1:0]  i_rx_shift,
  input  wire                    i_sclk_rise,
  input  wire                    i_cs_n,
  input  wire                    i_clk,
  input  wire                    i_rst_n
);

  localparam CNT_W = $clog2(BYTE_WIDTH + 1);

  // Counter: reset on CS deassert or byte complete, increment on SCLK rise
  wire [CNT_W-1:0] w_cnt;
  wire              w_byte_complete = (w_cnt == BYTE_WIDTH[CNT_W-1:0]);
  wire              w_cnt_en   = i_cs_n | i_sclk_rise | w_byte_complete;
  wire [CNT_W-1:0] w_cnt_next = (i_cs_n | w_byte_complete) ? {CNT_W{1'b0}}
                                                            : (w_cnt + {{(CNT_W-1){1'b0}}, 1'b1});

  register #(.N(CNT_W)) cnt_reg (
    .o_Q(w_cnt),
    .i_D(w_cnt_next),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(w_cnt_en)
  );

  // RX output latch: capture shift register on byte complete
  register #(.N(BYTE_WIDTH)) rx_latch (
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
