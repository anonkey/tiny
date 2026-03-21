`default_nettype none

// ALU operand B mux — selects between rs2 data and sign-extended imm6.
// Shared by cpu and half_cpu.

module alu_operand_mux (
  output wire [7:0] o_alu_b,
  input  wire [7:0] i_rs2_data,
  input  wire [5:0] i_imm6,
  input  wire       i_sel       // 0 = rs2, 1 = sign-extended imm6
);

  wire [15:0] w_mux_in;
  assign w_mux_in = {{2{i_imm6[5]}}, i_imm6, i_rs2_data};

  mux #(.WAY(2), .WIRE(8)) alu_b_mux (
    .i_in(w_mux_in),
    .i_ctrl(i_sel),
    .o_out(o_alu_b)
  );

endmodule
