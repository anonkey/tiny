module register(Q, D, clk, rst_n, en);

   parameter N = 8;

   output [N-1:0] Q;
   input  [N-1:0] D;
   input          clk;
   input          rst_n;
   input          en;

   wire [N-1:0] Qn;

   genvar i;
   for (i = 0; i < N; i = i + 1) begin : b
      dff ff(
         .Q(Q[i]),
         .Qn(Qn[i]),
         .D(D[i]),
         .clk(clk),
         .rst_n(rst_n),
         .en(en)
      );
   end

endmodule

// Backward-compatible 8-bit wrapper
module register_8bit (
   output [7:0] Q,
   input  [7:0] D,
   input        clk,
   input        rst_n,
   input        en
);

   register #(.N(8)) reg8(
      .Q(Q),
      .D(D),
      .clk(clk),
      .rst_n(rst_n),
      .en(en)
   );

endmodule
