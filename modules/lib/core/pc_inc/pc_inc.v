`default_nettype none

module pc_inc(o_pc_next, i_pc);

   parameter N = 8;

   output [N-1:0] o_pc_next;
   input  [N-1:0] i_pc;

   wire [N:0] w_carry;
   assign w_carry[0] = 1'b1;

   genvar k;
   for (k = 0; k < N; k = k + 1) begin : ha
      assign o_pc_next[k] = i_pc[k] ^ w_carry[k];
      assign w_carry[k+1] = i_pc[k] & w_carry[k];
   end

endmodule
