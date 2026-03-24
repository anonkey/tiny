`default_nettype none
`timescale 1ns / 1ps

module tb_spi_shift_tx ();

  initial begin
    $dumpvars(0, tb_spi_shift_tx);
    #1;
  end

  reg        clk = 0;
  reg        rst_n = 0;
  reg  [7:0] data = 0;
  reg        load = 0;
  reg        shift_en = 0;
  reg        active = 0;

  wire       miso;

  spi_shift_tx dut (
    .o_miso(miso),
    .i_data(data),
    .i_load(load),
    .i_shift_en(shift_en),
    .i_active(active),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
