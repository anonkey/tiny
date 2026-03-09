module pc(
   output [7:0] o_pc,
   input  [7:0] i_load_addr,
   input        i_load,
   input        i_clk,
   input        i_rst_n
);

   // PC + 1 via Kogge-Stone (a=o_pc, b=1, sub=0)
   wire [8:0] w_pc_plus1;
   kogge_stone #(.N(8)) inc(
      .o_S(w_pc_plus1),
      .i_A(o_pc),
      .i_B(8'b1),
      .i_sub(1'b0)
   );

   // Select between PC+1 (normal) and i_load_addr (jump)
   wire [15:0] w_mux_in;
   wire [7:0]  w_next_pc;
   assign w_mux_in = {i_load_addr, w_pc_plus1[7:0]};

   mux #(.WAY(2), .WIRE(8)) pc_mux(
      .i_in(w_mux_in),
      .i_ctrl(i_load),
      .o_out(w_next_pc)
   );

   // Register holds current PC
   register #(.N(8)) pc_reg(
      .o_Q(o_pc),
      .i_D(w_next_pc),
      .i_clk(i_clk),
      .i_rst_n(i_rst_n),
      .i_en(1'b1)
   );

endmodule
