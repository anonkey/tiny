`default_nettype none
`timescale 1ns / 1ps

module tb_cpu_fsm ();

  initial begin
    $dumpvars(0, tb_cpu_fsm);
    #1;
  end

  reg         clk = 0;
  reg         rst_n = 0;

  // Datapath inputs
  reg  [7:0]  pc = 0;
  reg  [7:0]  alu_result = 0;
  reg  [7:0]  rs2_data = 0;
  reg         is_load = 0;
  reg         is_store = 0;

  // Memory interface inputs
  reg         mem_done = 0;
  reg         timeout = 0;

  // Outputs
  wire        mem_req;
  wire [1:0]  mem_op;
  wire [7:0]  mem_addr;
  wire [7:0]  mem_wdata;
  wire        instr_en;
  wire        reg_we;
  wire        pc_en;
  wire        load_data_sel;
  wire [2:0]  state;

  cpu_fsm dut (
    .o_mem_req(mem_req),
    .o_mem_op(mem_op),
    .o_mem_addr(mem_addr),
    .o_mem_wdata(mem_wdata),
    .i_mem_done(mem_done),

    .o_instr_en(instr_en),
    .o_reg_we(reg_we),
    .o_pc_en(pc_en),
    .o_load_data_sel(load_data_sel),

    .o_state(state),

    .i_pc(pc),
    .i_alu_result(alu_result),
    .i_rs2_data(rs2_data),
    .i_is_load(is_load),
    .i_is_store(is_store),

    .i_timeout(timeout),

    .i_clk(clk),
    .i_rst_n(rst_n)
  );

endmodule
