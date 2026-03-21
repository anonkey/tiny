`default_nettype none

// Zero flag detector — outputs 1 when all input bits are zero.
// Parameterized width.

module zero_flag #(
  parameter N = 8
)(
  output wire o_zero,
  input  wire [N-1:0] i_data
);

  assign o_zero = ~|i_data;

endmodule
