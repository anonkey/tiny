`default_nettype none
`timescale 1ns / 1ps

module tb_alu ();

  initial begin
    $dumpfile("tb_alu.fst");
    $dumpvars(0, tb_alu);
    #1;
  end

  reg [7:0] a;
  reg [7:0] b;
  reg [3:0] opcode;
  wire [7:0] result;
  wire carry;

  alu dut (
    .o_result(result),
    .o_carry(carry),
    .i_a(a),
    .i_b(b),
    .i_opcode(opcode)
  );

endmodule
