`default_nettype none
`timescale 1ns / 1ps

module tb_mem_ctrl ();

  initial begin
    $dumpvars(0, tb_mem_ctrl);
    #1;
  end

  reg         clk, rst_n;
  reg  [7:0]  spi_rx_data;
  reg         spi_byte_done;
  reg         mem_req;
  reg  [1:0]  mem_op;
  reg  [7:0]  mem_addr;
  reg  [7:0]  mem_wdata;
  wire [7:0]  spi_tx_data;
  wire        spi_tx_load;
  wire        cs_n;
  wire [15:0] read_data;
  wire        mem_done;
  wire        timeout;
  wire [3:0]  state;

  mem_ctrl dut (
    .o_spi_tx_data(spi_tx_data),
    .o_spi_tx_load(spi_tx_load),
    .i_spi_rx_data(spi_rx_data),
    .i_spi_byte_done(spi_byte_done),
    .o_cs_n(cs_n),
    .o_read_data(read_data),
    .i_mem_req(mem_req),
    .i_mem_op(mem_op),
    .i_mem_addr(mem_addr),
    .i_mem_wdata(mem_wdata),
    .o_mem_done(mem_done),
    .o_timeout(timeout),
    .o_state(state),
    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
