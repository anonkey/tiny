module cam(output [4:0]	out,
	   output reg	found,

	   input	clk,
	   input	enable,
	   input	rst_n,
	   input	write,
	   input [4:0]	addr,
	   input [7:0]	data);

   parameter NB_MEM = 16;
   parameter SIZE_ADDR = 4;

   reg [7:0] mem [0:NB_MEM-1];
   wire [SIZE_ADDR-1:0] ret;

   /* verilator lint_off UNUSEDSIGNAL */
   wire	   _ignore = addr[4];

   wire [NB_MEM-1:0] match;
   wire [SIZE_ADDR-1:0] addr_out [0:NB_MEM-1];

   genvar i;
   generate
      for (i = 0; i < NB_MEM; i = i + 1)
	begin : gen_match
	   assign match[i] = (mem[i] == data);
	   assign addr_out[i] = match[i] ? i[SIZE_ADDR-1:0] : {SIZE_ADDR{1'b0}};
	end
   endgenerate

   assign ret = write ? 4'b0 :
		addr_out[0] | addr_out[1] | addr_out[2] | addr_out[3] |
		addr_out[4] | addr_out[5] | addr_out[6] | addr_out[7] |
		addr_out[8] | addr_out[9] | addr_out[10] | addr_out[11] |
		addr_out[12] | addr_out[13] | addr_out[14] | addr_out[15];

   always @(posedge clk or negedge rst_n)
     begin

	if (~rst_n)
	  begin
	     found <= 0;
	     /*
	     mem[0] <= 8'h00;
	     mem[1] <= 8'h00;
	     mem[2] <= 8'h00;
	     mem[3] <= 8'h00;
	     mem[4] <= 8'h00;
	     mem[5] <= 8'h00;
	     mem[6] <= 8'h00;
	     mem[7] <= 8'h00;
	     mem[8] <= 8'h00;
	     mem[9] <= 8'h00;
	     mem[10] <= 8'h00;
	     mem[11] <= 8'h00;
	     mem[12] <= 8'h00;
	     mem[13] <= 8'h00;
	     mem[14] <= 8'h00;
	     mem[15] <= 8'h00;
	      */
	  end

	else if (write & enable)
	  mem[addr[SIZE_ADDR-1:0]] <= data;

	else if (enable)
	  begin
	     found <= |match;
	  end

     end

   assign out = {1'b0, ret};
endmodule
