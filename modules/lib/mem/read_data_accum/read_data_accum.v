`default_nettype none

// Read data accumulator — assembles 16-bit word from individual RX bytes.
// FETCH: 2 RX bytes → {hi, lo}
// LOAD:  1 RX byte  → lo only (hi unchanged)

module read_data_accum (
  output wire [15:0] o_read_data,
  input  wire [7:0]  i_rx_byte,
  input  wire        i_latch_hi,   // latch rx_byte into high byte
  input  wire        i_latch_lo,   // latch rx_byte into low byte
  input  wire        i_clk,
  input  wire        i_rst_n
);

  wire [7:0] r_hi, r_lo;

  register #(.N(8)) hi_reg (
    .o_Q(r_hi),
    .i_D(i_rx_byte),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(i_latch_hi)
  );

  register #(.N(8)) lo_reg (
    .o_Q(r_lo),
    .i_D(i_rx_byte),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(i_latch_lo)
  );

  assign o_read_data = {r_hi, r_lo};

endmodule
