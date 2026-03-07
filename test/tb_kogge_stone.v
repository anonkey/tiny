`default_nettype none
`timescale 1ns / 1ps

module tb_kogge_stone ();

  initial begin
    $dumpfile("tb_kogge_stone.fst");
    $dumpvars(0, tb_kogge_stone);
    #1;
  end

  reg [3:0] input_A;
  reg [3:0] input_B;
  reg sub;
  wire [4:0] output_S;

  kogge_stone #(.N(4)) dut (
    .output_S(output_S),
    .input_A(input_A),
    .input_B(input_B),
    .sub(sub)
  );

endmodule
