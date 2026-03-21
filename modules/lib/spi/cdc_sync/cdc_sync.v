`default_nettype none

// CDC synchronizer — N-stage FF chain for clock domain crossing.
// Parameterized depth (default 2). Output is the synchronized signal.

module cdc_sync #(
  parameter STAGES = 2
)(
  output wire o_sync,
  input  wire i_async,
  input  wire i_clk,
  input  wire i_rst_n
);

  wire [STAGES-1:0] w_chain;

  // First stage
  dff ff0 (
    .o_Q(w_chain[0]), .o_Qn(),
    .i_D(i_async),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // Remaining stages
  genvar i;
  for (i = 1; i < STAGES; i = i + 1) begin : stage
    dff ff (
      .o_Q(w_chain[i]), .o_Qn(),
      .i_D(w_chain[i-1]),
      .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
    );
  end

  assign o_sync = w_chain[STAGES-1];

endmodule

// Edge detector — detects rising and/or falling edges of a synchronized signal.
// Takes the synchronized signal, adds one pipeline stage to create a delayed copy.

module edge_detect (
  output wire o_rise,
  output wire o_fall,
  input  wire i_sync,
  input  wire i_clk,
  input  wire i_rst_n
);

  wire w_prev;

  dff prev_ff (
    .o_Q(w_prev), .o_Qn(),
    .i_D(i_sync),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  assign o_rise = i_sync & ~w_prev;
  assign o_fall = ~i_sync & w_prev;

endmodule
