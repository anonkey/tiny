`default_nettype none
`timescale 1ns / 1ps

module tb_mem_ctrl ();

  initial begin
    $dumpfile("../artifacts/mem_ctrl/tb_mem_ctrl.fst");
    $dumpvars(0, tb_mem_ctrl);
    #1;
  end

  reg         clk, rst_n;
  reg         spi_rx_done;
  reg         mem_req;
  reg  [1:0]  mem_op;
  reg  [7:0]  mem_addr;
  reg  [7:0]  mem_wdata;
  wire [15:0] spi_tx_data;
  wire        spi_tx_load;
  wire        mem_done;
  wire [2:0]  state;

  mem_ctrl dut (
    .o_spi_tx_data(spi_tx_data),
    .o_spi_tx_load(spi_tx_load),
    .i_spi_rx_done(spi_rx_done),
    .i_mem_req(mem_req),
    .i_mem_op(mem_op),
    .i_mem_addr(mem_addr),
    .i_mem_wdata(mem_wdata),
    .o_mem_done(mem_done),
    .o_state(state),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
