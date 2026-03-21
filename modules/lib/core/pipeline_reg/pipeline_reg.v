`default_nettype none

// Pipeline register — latches i_D when i_latch is high, holds otherwise.
// Parameterized width. Uses register primitive internally.

module pipeline_reg #(
  parameter N = 8
)(
  output wire [N-1:0] o_Q,
  input  wire [N-1:0] i_D,
  input  wire         i_latch,
  input  wire         i_clk,
  input  wire         i_rst_n
);

  register #(.N(N)) reg_inst (
    .o_Q(o_Q),
    .i_D(i_latch ? i_D : o_Q),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(1'b1)
  );

endmodule

// 1-bit pipeline register variant using dff.

module pipeline_dff (
  output wire o_Q,
  input  wire i_D,
  input  wire i_latch,
  input  wire i_clk,
  input  wire i_rst_n
);

  dff ff (
    .o_Q(o_Q), .o_Qn(),
    .i_D(i_latch ? i_D : o_Q),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

endmodule
