module ks_black(P, G, Pi, Pj, Gi, Gj);
   output P, G;
   input  Pi, Pj, Gi, Gj;

   assign P = Pi & Pj;
   assign G = Gi | (Pi & Gj);

endmodule

module ks_green(C_out, Pi, Gi, C_in);
   output C_out;
   input  Pi, Gi, C_in;

   assign C_out = Gi | (Pi & C_in);

endmodule

module kogge_stone(output_S, input_A, input_B, sub);

   parameter N = 8;

   output [N:0]   output_S;
   input  [N-1:0] input_A, input_B;
   input           sub;

   function integer log2;
      input integer value;
      begin
         value = value - 1;
         for (log2 = 0; value > 0; log2 = log2 + 1)
           value = value >> 1;
      end
   endfunction

   localparam STAGES = log2(N);

   wire [N-1:0] A, B;
   wire         Cin;

   assign A = input_A;
   assign B = input_B ^ {N{sub}};
   assign Cin = sub;

   wire [N:0] out;
   assign output_S = out;

   // Stage 0: initial P and G
   wire [N-1:0] P0, G0;
   assign P0 = A ^ B;
   assign G0 = A & B;

   wire [N-1:0] P [0:STAGES];
   wire [N-1:0] G [0:STAGES];
   assign P[0] = P0;
   assign G[0] = G0;

   // Stage 1 (span 1)
   genvar i;
   for (i = 0; i < N; i = i + 1) begin : s1
      if (i < 1) begin : pass
         assign P[1][i] = P[0][i];
         assign G[1][i] = G[0][i];
      end else begin : blk
         ks_black u_blk(.P(P[1][i]), .G(G[1][i]),
                        .Pi(P[0][i]), .Pj(P[0][i-1]),
                        .Gi(G[0][i]), .Gj(G[0][i-1]));
      end
   end

   // Stage 2 (span 2)
   /* verilator lint_off GENUNNAMED */
   if (STAGES >= 2) begin
      for (i = 0; i < N; i = i + 1) begin : s2
         if (i < 2) begin : pass
            assign P[2][i] = P[1][i];
            assign G[2][i] = G[1][i];
         end else begin : blk
            ks_black u_blk(.P(P[2][i]), .G(G[2][i]),
                           .Pi(P[1][i]), .Pj(P[1][i-2]),
                           .Gi(G[1][i]), .Gj(G[1][i-2]));
         end
      end
   end

   // Stage 3 (span 4)
   if (STAGES >= 3) begin
      for (i = 0; i < N; i = i + 1) begin : s3
         if (i < 4) begin : pass
            assign P[3][i] = P[2][i];
            assign G[3][i] = G[2][i];
         end else begin : blk
            ks_black u_blk(.P(P[3][i]), .G(G[3][i]),
                           .Pi(P[2][i]), .Pj(P[2][i-4]),
                           .Gi(G[2][i]), .Gj(G[2][i-4]));
         end
      end
   end

   // Stage 4 (span 8)
   if (STAGES >= 4) begin
      for (i = 0; i < N; i = i + 1) begin : s4
         if (i < 8) begin : pass
            assign P[4][i] = P[3][i];
            assign G[4][i] = G[3][i];
         end else begin : blk
            ks_black u_blk(.P(P[4][i]), .G(G[4][i]),
                           .Pi(P[3][i]), .Pj(P[3][i-8]),
                           .Gi(G[3][i]), .Gj(G[3][i-8]));
         end
      end
   end

   // Stage 5 (span 16)
   if (STAGES >= 5) begin
      for (i = 0; i < N; i = i + 1) begin : s5
         if (i < 16) begin : pass
            assign P[5][i] = P[4][i];
            assign G[5][i] = G[4][i];
         end else begin : blk
            ks_black u_blk(.P(P[5][i]), .G(G[5][i]),
                           .Pi(P[4][i]), .Pj(P[4][i-16]),
                           .Gi(G[4][i]), .Gj(G[4][i-16]));
         end
      end
   end

   // Carry generation
   wire [N:0] C;
   assign C[0] = Cin;

   for (i = 0; i < N; i = i + 1) begin : carry
      ks_green grn(
         .C_out(C[i+1]),
         .Pi(P[STAGES][i]),
         .Gi(G[STAGES][i]),
         .C_in(C[0])
      );
   end

   // Sum
   for (i = 0; i < N; i = i + 1) begin : sum
      assign out[i] = P0[i] ^ C[i];
   end
   assign out[N] = C[N];

endmodule

// Backward-compatible 8-bit wrapper
module kogge_stone_cin (output_S, input_A, input_B, sub);
   output [8:0] output_S;
   input         sub;
   input [7:0]   input_A, input_B;

   kogge_stone #(.N(8)) ks(
      .output_S(output_S),
      .input_A(input_A),
      .input_B(input_B),
      .sub(sub)
   );

endmodule
