module regfile(rd1, rd2, wd, raddr1, raddr2, waddr, we, clk, rst_n);

   parameter NREG = 8;
   parameter WIDTH = 8;

   localparam ADDR = $clog2(NREG);

   output [WIDTH-1:0] rd1;
   output [WIDTH-1:0] rd2;
   input  [WIDTH-1:0] wd;
   input  [ADDR-1:0]  raddr1;
   input  [ADDR-1:0]  raddr2;
   input  [ADDR-1:0]  waddr;
   input               we;
   input               clk;
   input               rst_n;

   // Write-enable per register: demux the `we` signal
   wire [NREG-1:0] we_dec;
   demux #(.WAY(NREG), .WIRE(1)) we_demux (
      .in(we),
      .ctrl(waddr),
      .out(we_dec)
   );

   // Instantiate NREG registers
   wire [NREG*WIDTH-1:0] reg_out;
   genvar i;
   for (i = 0; i < NREG; i = i + 1) begin : r
      register #(.N(WIDTH)) reg_i (
         .Q(reg_out[i*WIDTH +: WIDTH]),
         .D(wd),
         .clk(clk),
         .rst_n(rst_n),
         .en(we_dec[i])
      );
   end

   mux #(.WAY(NREG), .WIRE(WIDTH)) rd1_mux (
      .in(reg_out),
      .ctrl(raddr1),
      .out(rd1)
   );

   // --- Read port 2: same bus, second mux ---
   mux #(.WAY(NREG), .WIRE(WIDTH)) rd2_mux (
      .in(reg_out),
      .ctrl(raddr2),
      .out(rd2)
   );

endmodule
