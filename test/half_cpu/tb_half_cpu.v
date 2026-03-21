`default_nettype none
`timescale 1ns / 1ps

module tb_half_cpu ();

  initial begin
    $dumpfile("../artifacts/tb_half_cpu.fst");
    $dumpvars(0, tb_half_cpu);
    #1;
  end

  reg         clk, rst_n;
  reg  [15:0] spi_rx_data;
  reg         spi_rx_done;
  wire [15:0] spi_tx_data;
  wire        spi_tx_load;
  wire [7:0]  pc_out, alu_out;
  wire [5:0]  state;

  half_cpu dut (
    .o_pc(pc_out),
    .o_alu(alu_out),
    .o_state(state),
    .o_spi_tx_data(spi_tx_data),
    .o_spi_tx_load(spi_tx_load),
    .i_spi_rx_data(spi_rx_data),
    .i_spi_rx_done(spi_rx_done),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
