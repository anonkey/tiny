module dff (Q, Qn, D, clk, rst_n, en);
   output reg Q;
   output     Qn;
   input      D, clk, rst_n, en;

   assign Qn = ~Q;

   always @(posedge clk or negedge rst_n) begin
      if (!rst_n)
         Q <= 1'b0;
      else if (en)
         Q <= D;
   end

endmodule
