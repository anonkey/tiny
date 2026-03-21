`default_nettype none

// Memory controller — translates abstract memory requests into
// byte-by-byte SPI transactions (nvSRAM-compatible).
// Drives CS_n to frame variable-length commands.
// Structural: no always blocks.

module mem_ctrl (
  // SPI byte interface
  output wire [7:0]  o_spi_tx_data,
  output wire        o_spi_tx_load,
  input  wire [7:0]  i_spi_rx_data,
  input  wire        i_spi_byte_done,

  // CS control
  output wire        o_cs_n,

  // Accumulated read data (for cpu: instruction fetch / load)
  output wire [15:0] o_read_data,

  // Memory bus (from cpu_fsm)
  input  wire        i_mem_req,       // pulse: start operation
  input  wire [1:0]  i_mem_op,        // 00=FETCH, 01=LOAD, 10=STORE
  input  wire [7:0]  i_mem_addr,      // address
  input  wire [7:0]  i_mem_wdata,     // write data (STORE only)
  output wire        o_mem_done,      // pulse: operation complete

  // Debug
  output wire [3:0]  o_state,

  // System
  input  wire        i_clk,
  input  wire        i_rst_n
);

  // --- Memory operations ---
  localparam [1:0] MEM_OP_FETCH = 2'b00;
  localparam [1:0] MEM_OP_LOAD  = 2'b01;
  localparam [1:0] MEM_OP_STORE = 2'b10;

  // --- SPI commands (nvSRAM-compatible) ---
  localparam [7:0] CMD_IFETCH = 8'h03;  // READ
  localparam [7:0] CMD_LOAD   = 8'h0B;  // FAST_READ
  localparam [7:0] CMD_STORE  = 8'h02;  // WRITE
  localparam [7:0] CMD_WREN   = 8'h06;  // WREN

  // --- States (4-bit, 16 states) ---
  localparam [3:0] S_IDLE       = 4'd0;
  localparam [3:0] S_WREN_LOAD  = 4'd1;
  localparam [3:0] S_WREN_WAIT  = 4'd2;
  localparam [3:0] S_WREN_CS_HI = 4'd3;
  localparam [3:0] S_CMD_LOAD   = 4'd4;
  localparam [3:0] S_CMD_WAIT   = 4'd5;
  localparam [3:0] S_ADDR_LOAD  = 4'd6;
  localparam [3:0] S_ADDR_WAIT  = 4'd7;
  localparam [3:0] S_WDATA_LOAD = 4'd8;
  localparam [3:0] S_WDATA_WAIT = 4'd9;
  localparam [3:0] S_DUMMY_LOAD = 4'd10;
  localparam [3:0] S_DUMMY_WAIT = 4'd11;
  localparam [3:0] S_RX1_LOAD   = 4'd12;
  localparam [3:0] S_RX1_WAIT   = 4'd13;
  localparam [3:0] S_RX2_LOAD   = 4'd14;
  localparam [3:0] S_RX2_WAIT   = 4'd15;

  // =====================================================================
  // State register
  // =====================================================================
  wire [3:0] r_state;
  assign o_state = r_state;

  // State decode helpers
  wire w_in_idle       = (r_state == S_IDLE);
  wire w_in_wren_load  = (r_state == S_WREN_LOAD);
  wire w_in_wren_wait  = (r_state == S_WREN_WAIT);
  wire w_in_wren_cs_hi = (r_state == S_WREN_CS_HI);
  wire w_in_cmd_load   = (r_state == S_CMD_LOAD);
  wire w_in_cmd_wait   = (r_state == S_CMD_WAIT);
  wire w_in_addr_load  = (r_state == S_ADDR_LOAD);
  wire w_in_addr_wait  = (r_state == S_ADDR_WAIT);
  wire w_in_wdata_load = (r_state == S_WDATA_LOAD);
  wire w_in_wdata_wait = (r_state == S_WDATA_WAIT);
  wire w_in_dummy_load = (r_state == S_DUMMY_LOAD);
  wire w_in_dummy_wait = (r_state == S_DUMMY_WAIT);
  wire w_in_rx1_load   = (r_state == S_RX1_LOAD);
  wire w_in_rx1_wait   = (r_state == S_RX1_WAIT);
  wire w_in_rx2_load   = (r_state == S_RX2_LOAD);
  wire w_in_rx2_wait   = (r_state == S_RX2_WAIT);

  // =====================================================================
  // Latched request registers (captured on IDLE & mem_req)
  // =====================================================================
  wire [1:0] r_op;
  wire [7:0] r_addr;
  wire [7:0] r_wdata;
  wire       w_latch_en = w_in_idle & i_mem_req;

  register #(.N(2)) op_reg (
    .o_Q(r_op),
    .i_D(w_latch_en ? i_mem_op : r_op),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  register #(.N(8)) addr_reg (
    .o_Q(r_addr),
    .i_D(w_latch_en ? i_mem_addr : r_addr),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  register #(.N(8)) wdata_reg (
    .o_Q(r_wdata),
    .i_D(w_latch_en ? i_mem_wdata : r_wdata),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // Derived operation flags
  wire w_is_fetch = (r_op == MEM_OP_FETCH);
  wire w_is_load  = (r_op == MEM_OP_LOAD);
  wire w_is_store = (r_op == MEM_OP_STORE);

  // =====================================================================
  // Opcode selection from r_op via mux
  // =====================================================================
  wire [7:0] w_opcode;

  // 4-way mux: index 0=FETCH(0x03), 1=LOAD(0x0B), 2=STORE(0x02), 3=unused
  wire [31:0] w_opcode_mux_in = {8'h00, CMD_STORE, CMD_LOAD, CMD_IFETCH};

  mux #(.WAY(4), .WIRE(8)) opcode_mux (
    .i_in(w_opcode_mux_in),
    .i_ctrl(r_op),
    .o_out(w_opcode)
  );

  // =====================================================================
  // Next-state logic
  // =====================================================================
  wire [3:0] w_next_state =
    // IDLE
    (w_in_idle & i_mem_req & (i_mem_op == MEM_OP_STORE))
                                              ? S_WREN_LOAD :
    (w_in_idle & i_mem_req)                   ? S_CMD_LOAD :
    w_in_idle                                 ? S_IDLE :
    // WREN sequence
    w_in_wren_load                            ? S_WREN_WAIT :
    (w_in_wren_wait & i_spi_byte_done)        ? S_WREN_CS_HI :
    w_in_wren_wait                            ? S_WREN_WAIT :
    w_in_wren_cs_hi                           ? S_CMD_LOAD :
    // CMD byte
    w_in_cmd_load                             ? S_CMD_WAIT :
    (w_in_cmd_wait & i_spi_byte_done)         ? S_ADDR_LOAD :
    w_in_cmd_wait                             ? S_CMD_WAIT :
    // ADDR byte
    w_in_addr_load                            ? S_ADDR_WAIT :
    (w_in_addr_wait & i_spi_byte_done & w_is_store)
                                              ? S_WDATA_LOAD :
    (w_in_addr_wait & i_spi_byte_done & w_is_load)
                                              ? S_DUMMY_LOAD :
    (w_in_addr_wait & i_spi_byte_done)        ? S_RX1_LOAD :
    w_in_addr_wait                            ? S_ADDR_WAIT :
    // WDATA byte (STORE)
    w_in_wdata_load                           ? S_WDATA_WAIT :
    (w_in_wdata_wait & i_spi_byte_done)       ? S_IDLE :
    w_in_wdata_wait                           ? S_WDATA_WAIT :
    // DUMMY byte (FAST_READ / LOAD)
    w_in_dummy_load                           ? S_DUMMY_WAIT :
    (w_in_dummy_wait & i_spi_byte_done)       ? S_RX1_LOAD :
    w_in_dummy_wait                           ? S_DUMMY_WAIT :
    // RX byte 1
    w_in_rx1_load                             ? S_RX1_WAIT :
    (w_in_rx1_wait & i_spi_byte_done & w_is_fetch)
                                              ? S_RX2_LOAD :
    (w_in_rx1_wait & i_spi_byte_done)         ? S_IDLE :
    w_in_rx1_wait                             ? S_RX1_WAIT :
    // RX byte 2 (FETCH only)
    w_in_rx2_load                             ? S_RX2_WAIT :
    (w_in_rx2_wait & i_spi_byte_done)         ? S_IDLE :
    w_in_rx2_wait                             ? S_RX2_WAIT :
    // Default
                                                S_IDLE;

  register #(.N(4)) state_reg (
    .o_Q(r_state), .i_D(w_next_state),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // CS_n output (registered)
  // CS is active-low. High only in IDLE and WREN_CS_HI.
  // Use o_Qn so reset gives o_cs_n=1 (deasserted).
  // =====================================================================
  wire w_cs_active = ~(w_in_idle | w_in_wren_cs_hi);

  dff cs_ff (
    .o_Q(), .o_Qn(o_cs_n),
    .i_D(w_cs_active),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // SPI TX data (8-bit, registered)
  // =====================================================================
  wire [7:0] w_next_spi_tx_data =
    w_in_wren_load  ? CMD_WREN :
    w_in_cmd_load   ? w_opcode :
    w_in_addr_load  ? r_addr :
    w_in_wdata_load ? r_wdata :
    w_in_dummy_load ? 8'h00 :
    (w_in_rx1_load | w_in_rx2_load) ? 8'h00 :
                      o_spi_tx_data;

  register #(.N(8)) spi_tx_data_reg (
    .o_Q(o_spi_tx_data), .i_D(w_next_spi_tx_data),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // SPI TX load (registered pulse) — fire on all *_LOAD states
  // =====================================================================
  wire w_next_spi_tx_load = w_in_wren_load | w_in_cmd_load | w_in_addr_load |
                            w_in_wdata_load | w_in_dummy_load |
                            w_in_rx1_load | w_in_rx2_load;

  dff spi_tx_load_ff (
    .o_Q(o_spi_tx_load), .o_Qn(),
    .i_D(w_next_spi_tx_load),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // Read data accumulator (16-bit from 2 RX bytes)
  // =====================================================================
  wire w_latch_hi = w_in_rx1_wait & i_spi_byte_done & w_is_fetch;
  wire w_latch_lo = (w_in_rx2_wait & i_spi_byte_done) |
                    (w_in_rx1_wait & i_spi_byte_done & ~w_is_fetch);

  read_data_accum rda (
    .o_read_data(o_read_data),
    .i_rx_byte(i_spi_rx_data),
    .i_latch_hi(w_latch_hi),
    .i_latch_lo(w_latch_lo),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  // =====================================================================
  // Memory done (registered pulse)
  // Fires when transitioning to IDLE from a terminal state.
  // =====================================================================
  wire w_next_mem_done = (w_in_wdata_wait & i_spi_byte_done) |
                         (w_in_rx1_wait & i_spi_byte_done & ~w_is_fetch) |
                         (w_in_rx2_wait & i_spi_byte_done);

  dff mem_done_ff (
    .o_Q(o_mem_done), .o_Qn(),
    .i_D(w_next_mem_done),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

endmodule
