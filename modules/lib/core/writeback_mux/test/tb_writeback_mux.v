`default_nettype none
`timescale 1ns / 1ps

module tb_writeback_mux ();

  initial begin
    $dumpvars(0, tb_writeback_mux);
    #1;
  end

  reg [7:0] alu_result;
  reg [7:0] imm8;
  reg [7:0] load_data;
  reg use_imm8;
  reg load_data_sel;
  wire [7:0] write_data;

  writeback_mux dut (
    .o_write_data(write_data),
    .i_alu_result(alu_result),
    .i_imm8(imm8),
    .i_load_data(load_data),
    .i_use_imm8(use_imm8),
    .i_load_data_sel(load_data_sel)
  );

endmodule
