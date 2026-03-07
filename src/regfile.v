module regfile(rd1, rd2, wd, raddr1, raddr2, waddr, we, clk, rst_n);

   parameter NREG = 8;
   parameter WIDTH = 8;

   function integer log2;
      input integer value;
      begin
         value = value - 1;
         for (log2 = 0; value > 0; log2 = log2 + 1)
           value = value >> 1;
      end
   endfunction

   localparam ADDR = log2(NREG);

   output [WIDTH-1:0] rd1;
   output [WIDTH-1:0] rd2;
   input  [WIDTH-1:0] wd;
   input  [ADDR-1:0]  raddr1;
   input  [ADDR-1:0]  raddr2;
   input  [ADDR-1:0]  waddr;
   input               we;
   input               clk;
   input               rst_n;

   // --- Register bank ---
   wire [WIDTH-1:0] reg_out [0:NREG-1];

   // Write-enable per register: demux the `we` signal
   wire [NREG-1:0] we_dec;
   demux #(.WAY(NREG), .WIRE(1)) we_demux (
      .in(we),
      .ctrl(waddr),
      .out(we_dec)
   );

   // Instantiate NREG registers
   genvar i;
   for (i = 0; i < NREG; i = i + 1) begin : r
      register #(.N(WIDTH)) reg_i (
         .Q(reg_out[i]),
         .D(wd),
         .clk(clk),
         .rst_n(rst_n),
         .en(we_dec[i])
      );
   end

   // --- Read port 1: mux all register outputs ---
   wire [NREG*WIDTH-1:0] rd_bus;
   genvar j;
   for (j = 0; j < NREG; j = j + 1) begin : flat
      assign rd_bus[j*WIDTH +: WIDTH] = reg_out[j];
   end

   mux #(.WAY(NREG), .WIRE(WIDTH)) rd1_mux (
      .in(rd_bus),
      .ctrl(raddr1),
      .out(rd1)
   );

   // --- Read port 2: same bus, second mux ---
   mux #(.WAY(NREG), .WIRE(WIDTH)) rd2_mux (
      .in(rd_bus),
      .ctrl(raddr2),
      .out(rd2)
   );

endmodule
