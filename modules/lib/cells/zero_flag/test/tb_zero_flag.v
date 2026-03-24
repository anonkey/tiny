`default_nettype none
`timescale 1ns / 1ps

module tb_zero_flag ();

  initial begin
    $dumpvars(0, tb_zero_flag);
    #1;
  end

  reg [7:0] data;
  wire zero;

  zero_flag #(.N(8)) dut (
    .o_zero(zero),
    .i_data(data)
  );

endmodule
