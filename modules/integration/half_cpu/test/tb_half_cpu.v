`default_nettype none
`timescale 1ns / 1ps

module tb_half_cpu ();

  initial begin
    $dumpvars(0, tb_half_cpu);
    #1;
  end

  reg        clk, rst_n;
  reg        sclk, miso;
  wire       mosi, cs_n;
  wire [7:0] pc_out, alu_out;
  wire [6:0] state;

  half_cpu dut (
    .o_pc(pc_out),
    .o_alu(alu_out),
    .o_state(state),
    .o_mosi(mosi),
    .i_miso(miso),
    .o_cs_n(cs_n),
    .i_sclk(sclk),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
