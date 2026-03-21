module alu(
   output [7:0] o_result,
   output       o_carry,
   input  [7:0] i_a,
   input  [7:0] i_b,
   input  [3:0] i_opcode
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
   wire [8:0] w_adder_out;
   kogge_stone #(.N(8)) ks(
      .o_S(w_adder_out),
      .i_A(i_a),
      .i_B(i_b),
      .i_sub(i_opcode[0])
   );

   // Compute each operation result
   wire [7:0] w_add,  w_sub;
   wire [7:0] w_and,  w_or,   w_xor;
   wire [7:0] w_not,  w_nand, w_nor, w_xnor;

   assign w_add  = w_adder_out[7:0];
   assign w_sub  = w_adder_out[7:0];
   assign w_and  = i_a & i_b;
   assign w_or   = i_a | i_b;
   assign w_xor  = i_a ^ i_b;
   assign w_not  = ~i_a;
   assign w_nand = ~(i_a & i_b);
   assign w_nor  = ~(i_a | i_b);
   assign w_xnor = ~(i_a ^ i_b);

   // 9-to-1 mux for result selection (4-bit opcode)
   // Using the existing mux module with WAY=16, WIRE=8
   // Tie unused inputs (opcodes 9-15) to zero
   wire [127:0] w_mux_in;
   assign w_mux_in = {
      8'b0,       // 1111
      8'b0,       // 1110
      8'b0,       // 1101
      8'b0,       // 1100
      8'b0,       // 1011
      8'b0,       // 1010
      8'b0,       // 1001
      w_xnor,     // 1000
      w_nor,      // 0111
      w_nand,     // 0110
      w_not,      // 0101
      w_xor,      // 0100
      w_or,       // 0011
      w_and,      // 0010
      w_sub,      // 0001
      w_add       // 0000
   };

   mux #(.WAY(16), .WIRE(8)) result_mux(
      .i_in(w_mux_in),
      .i_ctrl(i_opcode),
      .o_out(o_result)
   );

   // Carry only valid for ADD (0000) and SUB (0001)
   assign o_carry = w_adder_out[8] & ~i_opcode[3] & ~i_opcode[2] & ~i_opcode[1];

endmodule
