`default_nettype none

// SPI TX shift register — 8-bit, MSB-first.
// Loads i_data when i_load is high, shifts left on i_shift_en.
// A 1-clock guard suppresses stale shift_en after load, preventing
// the synchronizer's delayed falling edge from causing an extra shift.
// MISO output: tx_shift[7] when i_active, else 0.

module spi_shift_tx (
  output wire       o_miso,
  input  wire [7:0] i_data,
  input  wire       i_load,
  input  wire       i_shift_en,
  input  wire       i_active,    // CS active (active high)
  input  wire       i_clk,
  input  wire       i_rst_n
);

  // Guard: suppress shift on the clock after load
  wire w_just_loaded;

  dff guard_ff (
    .o_Q(w_just_loaded), .o_Qn(),
    .i_D(i_load),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  wire [7:0] w_shift;
  wire       w_shift_en_guarded = i_shift_en & ~w_just_loaded;
  wire       w_en   = i_load | w_shift_en_guarded;
  wire [7:0] w_next = i_load ? i_data : {w_shift[6:0], 1'b0};

  register #(.N(8)) shift_reg (
    .o_Q(w_shift),
    .i_D(w_next),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(w_en)
  );

  assign o_miso = i_active ? w_shift[7] : 1'b0;

endmodule
