`default_nettype none

// CPU FSM controller — pipeline stages: fetch, decode, execute,
// load/store (via memory controller), writeback, PC update.
// Structural: no always blocks.

module cpu_fsm (
  // Memory controller interface
  output wire        o_mem_req,       // pulse: request memory operation
  output wire [1:0]  o_mem_op,        // 00=FETCH, 01=LOAD, 10=STORE
  output wire [7:0]  o_mem_addr,      // address
  output wire [7:0]  o_mem_wdata,     // write data (STORE)
  input  wire        i_mem_done,      // pulse: operation complete

  // Control outputs to datapath
  output wire        o_instr_en,      // latch instruction from SPI RX
  output wire        o_reg_we,        // enable regfile write
  output wire        o_pc_en,         // enable PC advance
  output wire        o_load_data_sel, // 1 = writeback from memory (LOAD)

  // Debug
  output wire [2:0]  o_state,

  // Datapath inputs
  input  wire [7:0]  i_pc,
  input  wire [7:0]  i_alu_result,
  input  wire [7:0]  i_rs2_data,      // for STORE
  input  wire        i_is_load,       // decoder says LOAD
  input  wire        i_is_store,      // decoder says STORE

  // System
  input  wire        i_clk,
  input  wire        i_rst_n
);

  // --- Memory operations ---
  localparam [1:0] MEM_OP_FETCH = 2'b00;
  localparam [1:0] MEM_OP_LOAD  = 2'b01;
  localparam [1:0] MEM_OP_STORE = 2'b10;

  // --- States ---
  localparam [2:0] S_FETCH_REQ  = 3'd0;
  localparam [2:0] S_FETCH_WAIT = 3'd1;
  localparam [2:0] S_DECODE     = 3'd2;
  localparam [2:0] S_EXECUTE    = 3'd3;
  localparam [2:0] S_MEM_REQ    = 3'd4;
  localparam [2:0] S_MEM_WAIT   = 3'd5;
  localparam [2:0] S_WRITEBACK  = 3'd6;
  localparam [2:0] S_PC_UPDATE  = 3'd7;

  // =====================================================================
  // State register
  // =====================================================================
  wire [2:0] r_state;
  assign o_state = r_state;

  // State decode helpers
  wire w_in_fetch_req  = (r_state == S_FETCH_REQ);
  wire w_in_fetch_wait = (r_state == S_FETCH_WAIT);
  wire w_in_decode     = (r_state == S_DECODE);
  wire w_in_execute    = (r_state == S_EXECUTE);
  wire w_in_mem_req    = (r_state == S_MEM_REQ);
  wire w_in_mem_wait   = (r_state == S_MEM_WAIT);
  wire w_in_writeback  = (r_state == S_WRITEBACK);
  wire w_in_pc_update  = (r_state == S_PC_UPDATE);

  // =====================================================================
  // Next-state logic
  // =====================================================================
  wire [2:0] w_next_state =
    w_in_fetch_req                            ? S_FETCH_WAIT :
    (w_in_fetch_wait & i_mem_done)            ? S_DECODE :
    w_in_fetch_wait                           ? S_FETCH_WAIT :
    w_in_decode                               ? S_EXECUTE :
    (w_in_execute & (i_is_load | i_is_store)) ? S_MEM_REQ :
    w_in_execute                              ? S_WRITEBACK :
    w_in_mem_req                              ? S_MEM_WAIT :
    (w_in_mem_wait & i_mem_done)              ? S_WRITEBACK :
    w_in_mem_wait                             ? S_MEM_WAIT :
    w_in_writeback                            ? S_PC_UPDATE :
    w_in_pc_update                            ? S_FETCH_REQ :
                                                S_FETCH_REQ;

  register #(.N(3)) state_reg (
    .o_Q(r_state), .i_D(w_next_state),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // Latched datapath registers (update in S_EXECUTE, hold otherwise)
  // =====================================================================
  wire [7:0] r_alu_result, r_rs2_data;
  wire       r_is_load, r_is_store;

  pipeline_reg #(.N(8)) alu_result_reg (
    .o_Q(r_alu_result),
    .i_D(i_alu_result),
    .i_latch(w_in_execute),
    .i_clk(i_clk), .i_rst_n(i_rst_n)
  );

  pipeline_reg #(.N(8)) rs2_data_reg (
    .o_Q(r_rs2_data),
    .i_D(i_rs2_data),
    .i_latch(w_in_execute),
    .i_clk(i_clk), .i_rst_n(i_rst_n)
  );

  pipeline_dff is_load_ff (
    .o_Q(r_is_load),
    .i_D(i_is_load),
    .i_latch(w_in_execute),
    .i_clk(i_clk), .i_rst_n(i_rst_n)
  );

  pipeline_dff is_store_ff (
    .o_Q(r_is_store),
    .i_D(i_is_store),
    .i_latch(w_in_execute),
    .i_clk(i_clk), .i_rst_n(i_rst_n)
  );

  // =====================================================================
  // Memory request pulse (one cycle in FETCH_REQ and MEM_REQ states)
  // =====================================================================
  wire w_next_mem_req = w_in_fetch_req | w_in_mem_req;

  dff mem_req_ff (
    .o_Q(o_mem_req), .o_Qn(),
    .i_D(w_next_mem_req),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // Memory operation type (registered, hold between updates)
  // =====================================================================
  wire [1:0] w_next_mem_op =
    w_in_fetch_req                ? MEM_OP_FETCH :
    (w_in_mem_req & r_is_load)   ? MEM_OP_LOAD :
    (w_in_mem_req & r_is_store)  ? MEM_OP_STORE :
                                   o_mem_op;

  register #(.N(2)) mem_op_reg (
    .o_Q(o_mem_op), .i_D(w_next_mem_op),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // Memory address (registered, hold between updates)
  // =====================================================================
  wire [7:0] w_next_mem_addr =
    w_in_fetch_req ? i_pc :
    w_in_mem_req   ? r_alu_result :
                     o_mem_addr;

  register #(.N(8)) mem_addr_reg (
    .o_Q(o_mem_addr), .i_D(w_next_mem_addr),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // Memory write data (registered, hold between updates)
  // =====================================================================
  wire [7:0] w_next_mem_wdata =
    w_in_mem_req ? r_rs2_data :
                   o_mem_wdata;

  register #(.N(8)) mem_wdata_reg (
    .o_Q(o_mem_wdata), .i_D(w_next_mem_wdata),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // Pulse outputs
  // =====================================================================
  wire w_next_instr_en = w_in_fetch_wait & i_mem_done;

  dff instr_en_ff (
    .o_Q(o_instr_en), .o_Qn(),
    .i_D(w_next_instr_en),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  dff reg_we_ff (
    .o_Q(o_reg_we), .o_Qn(),
    .i_D(w_in_writeback),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  dff pc_en_ff (
    .o_Q(o_pc_en), .o_Qn(),
    .i_D(w_in_writeback),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  wire w_next_load_data_sel = (w_in_mem_wait & i_mem_done & r_is_load) |
                              (w_in_writeback & r_is_load);

  dff load_data_sel_ff (
    .o_Q(o_load_data_sel), .o_Qn(),
    .i_D(w_next_load_data_sel),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

endmodule
