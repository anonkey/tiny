`default_nettype none
`timescale 1ns / 1ps

module tb_pc_inc ();

  initial begin
    $dumpvars(0, tb_pc_inc);
    #1;
  end

  reg [7:0] pc;
  wire [7:0] pc_next;

  pc_inc #(.N(8)) dut (
    .o_pc_next(pc_next),
    .i_pc(pc)
  );

endmodule
