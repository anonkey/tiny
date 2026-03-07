module alu(
   output [7:0] result,
   output       carry,
   input  [7:0] a,
   input  [7:0] b,
   input  [3:0] opcode
);

   // Opcode encoding:
   // 0000 ADD
   // 0001 SUB
   // 0010 AND
   // 0011 OR
   // 0100 XOR
   // 0101 NOT (of a)
   // 0110 NAND
   // 0111 NOR
   // 1000 XNOR

   // Kogge-Stone adder for ADD/SUB
   wire [8:0] adder_out;
   kogge_stone #(.N(8)) ks(
      .output_S(adder_out),
      .input_A(a),
      .input_B(b),
      .sub(opcode[0])
   );

   // Compute each operation result
   wire [7:0] r_add,  r_sub;
   wire [7:0] r_and,  r_or,   r_xor;
   wire [7:0] r_not,  r_nand, r_nor, r_xnor;

   assign r_add  = adder_out[7:0];
   assign r_sub  = adder_out[7:0];
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
   wire [127:0] mux_in;
   assign mux_in = {
      8'b0,    // 1111
      8'b0,    // 1110
      8'b0,    // 1101
      8'b0,    // 1100
      8'b0,    // 1011
      8'b0,    // 1010
      8'b0,    // 1001
      r_xnor,  // 1000
      r_nor,   // 0111
      r_nand,  // 0110
      r_not,   // 0101
      r_xor,   // 0100
      r_or,    // 0011
      r_and,   // 0010
      r_sub,   // 0001
      r_add    // 0000
   };

   mux #(.WAY(16), .WIRE(8)) result_mux(
      .in(mux_in),
      .ctrl(opcode),
      .out(result)
   );

   // Carry only valid for ADD (0000) and SUB (0001)
   assign carry = adder_out[8] & ~opcode[3] & ~opcode[2] & ~opcode[1];

endmodule
