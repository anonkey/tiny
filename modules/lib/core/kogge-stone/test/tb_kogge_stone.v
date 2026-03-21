`default_nettype none
`timescale 1ns / 1ps

module tb_kogge_stone ();

  initial begin
    $dumpvars(0, tb_kogge_stone);
    #1;
  end

  reg [7:0] input_A;
  reg [7:0] input_B;
  reg sub;
  wire [8:0] output_S;

  kogge_stone #(.N(8)) dut (
    .o_S(output_S),
    .i_A(input_A),
    .i_B(input_B),
    .i_sub(sub)
  );

endmodule
