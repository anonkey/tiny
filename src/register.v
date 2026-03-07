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
