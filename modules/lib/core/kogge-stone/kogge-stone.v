module ks_black(o_P, o_G, i_Pi, i_Pj, i_Gi, i_Gj);
   output o_P, o_G;
   input  i_Pi, i_Pj, i_Gi, i_Gj;

   assign o_P = i_Pi & i_Pj;
   assign o_G = i_Gi | (i_Pi & i_Gj);

endmodule

module ks_green(o_C_out, i_Pi, i_Gi, i_C_in);
   output o_C_out;
   input  i_Pi, i_Gi, i_C_in;

   assign o_C_out = i_Gi | (i_Pi & i_C_in);

endmodule

module kogge_stone(o_S, i_A, i_B, i_sub);

   parameter N = 8;

   output [N:0]   o_S;
   input  [N-1:0] i_A, i_B;
   input           i_sub;

   function integer log2;
      input integer i_value;
      begin
         i_value = i_value - 1;
         for (log2 = 0; i_value > 0; log2 = log2 + 1)
           i_value = i_value >> 1;
      end
   endfunction

   localparam STAGES = log2(N);

   wire [N-1:0] w_A, w_B;
   wire         w_Cin;

   assign w_A = i_A;
   assign w_B = i_B ^ {N{i_sub}};
   assign w_Cin = i_sub;

   wire [N:0] w_out;
   assign o_S = w_out;

   // Stage 0: initial P and G
   wire [N-1:0] w_P0, w_G0;
   assign w_P0 = w_A ^ w_B;
   assign w_G0 = w_A & w_B;

   wire [N-1:0] w_P [0:STAGES];
   wire [N-1:0] w_G [0:STAGES];
   assign w_P[0] = w_P0;
   assign w_G[0] = w_G0;

   // Stage 1 (span 1)
   genvar i;
   for (i = 0; i < N; i = i + 1) begin : s1
      if (i < 1) begin : pass
         assign w_P[1][i] = w_P[0][i];
         assign w_G[1][i] = w_G[0][i];
      end else begin : blk
         ks_black u_blk(.o_P(w_P[1][i]), .o_G(w_G[1][i]),
                        .i_Pi(w_P[0][i]), .i_Pj(w_P[0][i-1]),
                        .i_Gi(w_G[0][i]), .i_Gj(w_G[0][i-1]));
      end
   end

   // Stage 2 (span 2)
   /* verilator lint_off GENUNNAMED */
   if (STAGES >= 2) begin
      for (i = 0; i < N; i = i + 1) begin : s2
         if (i < 2) begin : pass
            assign w_P[2][i] = w_P[1][i];
            assign w_G[2][i] = w_G[1][i];
         end else begin : blk
            ks_black u_blk(.o_P(w_P[2][i]), .o_G(w_G[2][i]),
                           .i_Pi(w_P[1][i]), .i_Pj(w_P[1][i-2]),
                           .i_Gi(w_G[1][i]), .i_Gj(w_G[1][i-2]));
         end
      end
   end

   // Stage 3 (span 4)
   if (STAGES >= 3) begin
      for (i = 0; i < N; i = i + 1) begin : s3
         if (i < 4) begin : pass
            assign w_P[3][i] = w_P[2][i];
            assign w_G[3][i] = w_G[2][i];
         end else begin : blk
            ks_black u_blk(.o_P(w_P[3][i]), .o_G(w_G[3][i]),
                           .i_Pi(w_P[2][i]), .i_Pj(w_P[2][i-4]),
                           .i_Gi(w_G[2][i]), .i_Gj(w_G[2][i-4]));
         end
      end
   end

   // Stage 4 (span 8)
   if (STAGES >= 4) begin
      for (i = 0; i < N; i = i + 1) begin : s4
         if (i < 8) begin : pass
            assign w_P[4][i] = w_P[3][i];
            assign w_G[4][i] = w_G[3][i];
         end else begin : blk
            ks_black u_blk(.o_P(w_P[4][i]), .o_G(w_G[4][i]),
                           .i_Pi(w_P[3][i]), .i_Pj(w_P[3][i-8]),
                           .i_Gi(w_G[3][i]), .i_Gj(w_G[3][i-8]));
         end
      end
   end

   // Stage 5 (span 16)
   if (STAGES >= 5) begin
      for (i = 0; i < N; i = i + 1) begin : s5
         if (i < 16) begin : pass
            assign w_P[5][i] = w_P[4][i];
            assign w_G[5][i] = w_G[4][i];
         end else begin : blk
            ks_black u_blk(.o_P(w_P[5][i]), .o_G(w_G[5][i]),
                           .i_Pi(w_P[4][i]), .i_Pj(w_P[4][i-16]),
                           .i_Gi(w_G[4][i]), .i_Gj(w_G[4][i-16]));
         end
      end
   end

   // Carry generation
   wire [N:0] w_C;
   assign w_C[0] = w_Cin;

   for (i = 0; i < N; i = i + 1) begin : carry
      ks_green grn(
         .o_C_out(w_C[i+1]),
         .i_Pi(w_P[STAGES][i]),
         .i_Gi(w_G[STAGES][i]),
         .i_C_in(w_C[0])
      );
   end

   // Sum
   for (i = 0; i < N; i = i + 1) begin : sum
      assign w_out[i] = w_P0[i] ^ w_C[i];
   end
   assign w_out[N] = w_C[N];

endmodule

// Backward-compatible 8-bit wrapper
module kogge_stone_cin (o_S, i_A, i_B, i_sub);
   output [8:0] o_S;
   input         i_sub;
   input [7:0]   i_A, i_B;

   kogge_stone #(.N(8)) ks(
      .o_S(o_S),
      .i_A(i_A),
      .i_B(i_B),
      .i_sub(i_sub)
   );

endmodule
