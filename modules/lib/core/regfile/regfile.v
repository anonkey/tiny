module regfile(o_rd1, o_rd2, i_wd, i_raddr1, i_raddr2, i_waddr, i_we, i_clk, i_rst_n);

   parameter NREG = 8;
   parameter WIDTH = 8;

   localparam ADDR = $clog2(NREG);

   output [WIDTH-1:0] o_rd1;
   output [WIDTH-1:0] o_rd2;
   input  [WIDTH-1:0] i_wd;
   input  [ADDR-1:0]  i_raddr1;
   input  [ADDR-1:0]  i_raddr2;
   input  [ADDR-1:0]  i_waddr;
   input               i_we;
   input               i_clk;
   input               i_rst_n;

   // Write-enable per register: demux the `we` signal
   wire [NREG-1:0] w_we_dec;
   demux #(.WAY(NREG), .WIRE(1)) we_demux (
      .i_in(i_we),
      .i_ctrl(i_waddr),
      .o_out(w_we_dec)
   );

   // Instantiate NREG registers
   wire [NREG*WIDTH-1:0] w_rd_bus;
   genvar i;
   for (i = 0; i < NREG; i = i + 1) begin : r
      register #(.N(WIDTH)) reg_i (
         .o_Q(w_rd_bus[i*WIDTH +: WIDTH]),
         .i_D(i_wd),
         .i_clk(i_clk),
         .i_rst_n(i_rst_n),
         .i_en(w_we_dec[i])
      );
   end

   // --- Read port 1 ---
   mux #(.WAY(NREG), .WIRE(WIDTH)) rd1_mux (
      .i_in(w_rd_bus),
      .i_ctrl(i_raddr1),
      .o_out(o_rd1)
   );

   // --- Read port 2: same bus, second mux ---
   mux #(.WAY(NREG), .WIRE(WIDTH)) rd2_mux (
      .i_in(w_rd_bus),
      .i_ctrl(i_raddr2),
      .o_out(o_rd2)
   );

endmodule
