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

  wire [1:0] w_sel;
  assign w_sel = i_load_data_sel ? 2'd2 :
                 i_use_imm8      ? 2'd1 : 2'd0;

  wire [31:0] w_mux_in;
  assign w_mux_in = {8'h00, i_load_data, i_imm8, i_alu_result};

  mux #(.WAY(4), .WIRE(8)) wb_mux (
    .i_in(w_mux_in),
    .i_ctrl(w_sel),
    .o_out(o_write_data)
  );

endmodule
