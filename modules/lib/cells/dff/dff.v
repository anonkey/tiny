`default_nettype none

// D flip-flop with async active-low reset and enable

module dff (o_Q, o_Qn, i_D, i_clk, i_rst_n, i_en);
   output reg o_Q;
   output     o_Qn;
   input      i_D, i_clk, i_rst_n, i_en;

   assign o_Qn = ~o_Q;

   always @(posedge i_clk or negedge i_rst_n) begin
      if (!i_rst_n)
         o_Q <= 1'b0;
      else if (i_en)
         o_Q <= i_D;
   end
endmodule
