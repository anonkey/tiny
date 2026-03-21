`default_nettype none

module pc(
   output [7:0] o_pc,
   input  [7:0] i_load_addr,
   input        i_load,
   input        i_en,
   input        i_clk,
   input        i_rst_n
);

   // PC + 1 via half-adder chain
   wire [7:0] w_pc_plus1;
   pc_inc #(.N(8)) inc(
      .o_pc_next(w_pc_plus1),
      .i_pc(o_pc)
   );

   // Select between PC+1 (normal) and i_load_addr (jump)
   wire [15:0] w_mux_in;
   wire [7:0]  w_next_pc;
   assign w_mux_in = {i_load_addr, w_pc_plus1};

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
      .i_en(i_en)
   );

endmodule
