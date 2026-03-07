module rom(data, addr);

   parameter DEPTH = 256;
   parameter WIDTH = 16;
   parameter MEMFILE = "";

   function integer log2;
      input integer value;
      begin
         value = value - 1;
         for (log2 = 0; value > 0; log2 = log2 + 1)
           value = value >> 1;
      end
   endfunction

   localparam ADDR_BITS = log2(DEPTH);

   output [WIDTH-1:0]      data;
   input  [ADDR_BITS-1:0]  addr;

   // ROM storage — initialized from hex file
   reg [WIDTH-1:0] mem [0:DEPTH-1];

   // Combinational read — no clock needed
   assign data = mem[addr];

   // Load contents at elaboration time
   initial begin
      if (MEMFILE != "")
         $readmemh(MEMFILE, mem);
   end

endmodule
