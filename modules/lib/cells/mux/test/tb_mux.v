`default_nettype none
`timescale 1ns / 1ps

module tb_mux ();

  initial begin
    $dumpvars(0, tb_mux);
    #1;
  end

  reg [63:0] data_in;
  reg [2:0]  ctrl;
  wire [7:0] out;

  mux #(.WAY(8), .WIRE(8)) dut (
    .i_in(data_in),
    .i_ctrl(ctrl),
    .o_out(out)
  );

endmodule
