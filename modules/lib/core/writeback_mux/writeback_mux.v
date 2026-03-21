`default_nettype none

// Writeback mux — 3-way select for register file write data.
// 00 = ALU result (R-type, ADDI)
// 01 = imm8 (LDI)
// 10 = load data (LOAD from memory)

module writeback_mux (
  output wire [7:0] o_write_data,
  input  wire [7:0] i_alu_result,
  input  wire [7:0] i_imm8,
  input  wire [7:0] i_load_data,
  input  wire       i_use_imm8,
  input  wire       i_load_data_sel
);

  // First mux: imm8 or ALU result
  wire [15:0] w_imm_alu_in;
  wire [7:0]  w_imm_or_alu;
  assign w_imm_alu_in = {i_imm8, i_alu_result};

  mux #(.WAY(2), .WIRE(8)) imm_alu_mux (
    .i_in(w_imm_alu_in),
    .i_ctrl(i_use_imm8),
    .o_out(w_imm_or_alu)
  );

  // Second mux: load data or first mux result
  wire [15:0] w_load_in;
  assign w_load_in = {i_load_data, w_imm_or_alu};

  mux #(.WAY(2), .WIRE(8)) load_mux (
    .i_in(w_load_in),
    .i_ctrl(i_load_data_sel),
    .o_out(o_write_data)
  );

endmodule
