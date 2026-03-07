module alu(
   output [7:0] result,
   input  [7:0] a,
   input  [7:0] b,
   input  [3:0] opcode
);

   // Opcode encoding: and convert
   // ADD  0000 -> 000
   // SUB  0001 -> 000
   // AND  0010 -> 001
   // OR   0011 -> 010
   // XOR  0100 -> 011
   // NOT  0101 -> 100
   // AND  0110 -> 101
   // NOR  0111 -> 110
   // XNOR 1000 -> 111

   // Kogge-Stone adder for ADD/SUB
   wire [7:0] adder_out;
   assign adder_out = opcode[0] ? a - b : a + b;

   // Compute each operation result
   wire [7:0] r_add_sub;
   wire [7:0] r_and,  r_or,   r_xor;
   wire [7:0] r_not,  r_nand, r_nor, r_xnor;

   assign r_add_sub  = adder_out; //merge add/sub (same output)
   assign r_and  = a & b;
   assign r_or   = a | b;
   assign r_xor  = a ^ b;
   assign r_not  = ~a;
   assign r_nand = ~(a & b);
   assign r_nor  = ~(a | b);
   assign r_xnor = ~(a ^ b);

   // 9-to-1 mux for result selection (4-bit opcode)
   // Using the existing mux module with WAY=16, WIRE=8
   // Tie unused inputs (opcodes 9-15) to zero
   localparam NB_OP = 8;
   localparam BIT_OP = 8;
   localparam SIZE_OP = NB_OP * BIT_OP;
   wire [SIZE_OP-1:0] mux_in;
   assign mux_in = {
      r_xnor,
      r_nor,
      r_nand,
      r_not,
      r_xor,
      r_or,
      r_and,
      r_add_sub
   };

   //conversion opcode 4 bit -> 3bit
   wire [2:0] converted_opcode;
   wire [3:0] tmp;
   assign tmp = opcode > 0 ? opcode - 4'b0001 : opcode;
   assign converted_opcode = tmp[2:0];

   mux #(.WAY(8), .WIRE(8)) result_mux(
      .in(mux_in),
      .ctrl(converted_opcode),
      .out(result)
   );

endmodule
