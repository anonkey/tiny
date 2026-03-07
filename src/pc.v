module pc(
   output [7:0] pc_out,
   input  [7:0] load_addr,
   input        load,
   input        clk,
   input        rst_n
);

   // PC + 1 via Kogge-Stone (a=pc_out, b=1, sub=0)
   wire [7:0] pc_plus1;
   assign pc_plus1 = pc_out + 1;

   // Select between PC+1 (normal) and load_addr (jump)
   wire [15:0] mux_in;
   wire [7:0]  next_pc;
   assign mux_in = {load_addr, pc_plus1};

   mux #(.WAY(2), .WIRE(8)) pc_mux(
      .in(mux_in),
      .ctrl(load),
      .out(next_pc)
   );

   // Register holds current PC
   register #(.N(8)) pc_reg(
      .Q(pc_out),
      .D(next_pc),
      .clk(clk),
      .rst_n(rst_n),
      .en(1'b1)
   );

endmodule
