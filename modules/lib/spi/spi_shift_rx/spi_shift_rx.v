`default_nettype none

// SPI RX shift register — 8-bit, MSB-first.
// Shifts in i_bit on i_shift_en (rising SCLK while CS active).

module spi_shift_rx (
  output wire [7:0] o_data,
  input  wire       i_bit,
  input  wire       i_shift_en,
  input  wire       i_clk,
  input  wire       i_rst_n
);

  wire [7:0] w_shift;
  wire [7:0] w_next = {w_shift[6:0], i_bit};

  register #(.N(8)) shift_reg (
    .o_Q(w_shift),
    .i_D(w_next),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(i_shift_en)
  );

  assign o_data = w_shift;

endmodule
