`default_nettype none
`timescale 1ns / 1ps

module tb_rom ();

  initial begin
    $dumpfile("tb_rom.fst");
    $dumpvars(0, tb_rom);
    #1;
  end

  reg [7:0] addr;
  wire [15:0] data;

  rom #(
    .DEPTH(256),
    .WIDTH(16),
    .MEMFILE("test_rom.hex")
  ) dut (
    .data(data),
    .addr(addr)
  );

endmodule
