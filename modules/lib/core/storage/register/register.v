`default_nettype none

module register(o_Q, i_D, i_clk, i_rst_n, i_en);

   parameter N = 8;

   output [N-1:0] o_Q;
   input  [N-1:0] i_D;
   input          i_clk;
   input          i_rst_n;
   input          i_en;

   wire [N-1:0] w_Qn;

   genvar i;
   for (i = 0; i < N; i = i + 1) begin : b
      dff ff(
         .o_Q(o_Q[i]),
         .o_Qn(w_Qn[i]),
         .i_D(i_D[i]),
         .i_clk(i_clk),
         .i_rst_n(i_rst_n),
         .i_en(i_en)
      );
   end

endmodule

// Backward-compatible 8-bit wrapper
module register_8bit (
   output [7:0] o_Q,
   input  [7:0] i_D,
   input        i_clk,
   input        i_rst_n,
   input        i_en
);

   register #(.N(8)) reg8(
      .o_Q(o_Q),
      .i_D(i_D),
      .i_clk(i_clk),
      .i_rst_n(i_rst_n),
      .i_en(i_en)
   );

endmodule
