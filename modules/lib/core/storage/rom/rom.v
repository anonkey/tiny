`default_nettype none

module rom(o_data, i_addr);

   parameter DEPTH = 256;
   parameter WIDTH = 16;
   parameter MEMFILE = "";

   function integer log2;
      input integer i_value;
      begin
         i_value = i_value - 1;
         for (log2 = 0; i_value > 0; log2 = log2 + 1)
           i_value = i_value >> 1;
      end
   endfunction

   localparam ADDR_BITS = log2(DEPTH);

   output [WIDTH-1:0]      o_data;
   input  [ADDR_BITS-1:0]  i_addr;

   // ROM storage — initialized from hex file
   reg [WIDTH-1:0] r_mem [0:DEPTH-1];

   // Combinational read — no clock needed
   assign o_data = r_mem[i_addr];

   // Load contents at elaboration time
   initial begin
      if (MEMFILE != "")
         $readmemh(MEMFILE, r_mem);
   end

endmodule
