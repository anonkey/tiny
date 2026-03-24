`default_nettype none
`timescale 1ns / 1ps

module tb_alu_operand_mux ();

  initial begin
    $dumpvars(0, tb_alu_operand_mux);
    #1;
  end

  reg [7:0] rs2_data;
  reg [5:0] imm6;
  reg sel;
  wire [7:0] alu_b;

  alu_operand_mux dut (
    .o_alu_b(alu_b),
    .i_rs2_data(rs2_data),
    .i_imm6(imm6),
    .i_sel(sel)
  );

endmodule
