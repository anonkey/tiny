`default_nettype none

// Memory controller — translates abstract memory requests into
// SPI two-phase half-duplex transactions (nvSRAM-compatible).
// Structural: no always blocks.

module mem_ctrl (
  // SPI TX interface
  output wire [15:0] o_spi_tx_data,
  output wire        o_spi_tx_load,

  // SPI RX interface
  input  wire        i_spi_rx_done,

  // Memory bus (from cpu_fsm)
  input  wire        i_mem_req,       // pulse: start operation
  input  wire [1:0]  i_mem_op,        // 00=FETCH, 01=LOAD, 10=STORE
  input  wire [7:0]  i_mem_addr,      // address
  input  wire [7:0]  i_mem_wdata,     // write data (STORE only)
  output wire        o_mem_done,      // pulse: operation complete

  // Debug
  output wire [2:0]  o_state,

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

  // --- States ---
  localparam [2:0] S_IDLE      = 3'd0;
  localparam [2:0] S_TX_WREN   = 3'd1;
  localparam [2:0] S_WAIT_WREN = 3'd2;
  localparam [2:0] S_TX_CMD    = 3'd3;
  localparam [2:0] S_WAIT_CMD  = 3'd4;
  localparam [2:0] S_TX_DATA   = 3'd5;
  localparam [2:0] S_WAIT_DATA = 3'd6;
  localparam [2:0] S_RX_WAIT   = 3'd7;

  // =====================================================================
  // State register
  // =====================================================================
  wire [2:0] r_state;
  assign o_state = r_state;

  // State decode helpers
  wire w_in_idle      = (r_state == S_IDLE);
  wire w_in_tx_wren   = (r_state == S_TX_WREN);
  wire w_in_wait_wren = (r_state == S_WAIT_WREN);
  wire w_in_tx_cmd    = (r_state == S_TX_CMD);
  wire w_in_wait_cmd  = (r_state == S_WAIT_CMD);
  wire w_in_tx_data   = (r_state == S_TX_DATA);
  wire w_in_wait_data = (r_state == S_WAIT_DATA);
  wire w_in_rx_wait   = (r_state == S_RX_WAIT);

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

  // Derived: is this a store operation?
  wire w_r_is_store = (r_op == MEM_OP_STORE);

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
  wire [2:0] w_next_state =
    (w_in_idle & i_mem_req & (i_mem_op == MEM_OP_STORE))
                                        ? S_TX_WREN :
    (w_in_idle & i_mem_req)             ? S_TX_CMD :
    w_in_idle                           ? S_IDLE :
    w_in_tx_wren                        ? S_WAIT_WREN :
    w_in_wait_wren                      ? S_TX_CMD :
    w_in_tx_cmd                         ? S_WAIT_CMD :
    (w_in_wait_cmd & w_r_is_store)      ? S_TX_DATA :
    w_in_wait_cmd                       ? S_RX_WAIT :
    w_in_tx_data                        ? S_WAIT_DATA :
    w_in_wait_data                      ? S_IDLE :
    (w_in_rx_wait & i_spi_rx_done)      ? S_IDLE :
    w_in_rx_wait                        ? S_RX_WAIT :
                                          S_IDLE;

  register #(.N(3)) state_reg (
    .o_Q(r_state), .i_D(w_next_state),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // SPI TX data (registered, hold between updates)
  // =====================================================================
  wire [15:0] w_next_spi_tx_data =
    w_in_tx_wren  ? {CMD_WREN, 8'h00} :
    w_in_tx_cmd   ? {w_opcode, r_addr} :
    w_in_tx_data  ? {8'h00, r_wdata} :
                    o_spi_tx_data;

  register #(.N(16)) spi_tx_data_reg (
    .o_Q(o_spi_tx_data), .i_D(w_next_spi_tx_data),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // SPI TX load (registered pulse)
  // =====================================================================
  wire w_next_spi_tx_load = w_in_tx_wren | w_in_tx_cmd | w_in_tx_data;

  dff spi_tx_load_ff (
    .o_Q(o_spi_tx_load), .o_Qn(),
    .i_D(w_next_spi_tx_load),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // Memory done (registered pulse)
  // =====================================================================
  wire w_next_mem_done = (w_in_rx_wait & i_spi_rx_done) | w_in_wait_data;

  dff mem_done_ff (
    .o_Q(o_mem_done), .o_Qn(),
    .i_D(w_next_mem_done),
    .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

endmodule
