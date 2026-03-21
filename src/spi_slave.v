`default_nettype none

// SPI slave — two-phase half-duplex protocol (structural)
//
// Phase 1 (TX): chip sends 16 bits on MISO = {cmd[7:0], addr[7:0]}
//   Commands: 0x01=IFETCH, 0x02=LOAD, 0x03=STORE
// Phase 2 (RX): chip receives 16 bits on MOSI = data
//   (for STORE, chip sends data on MISO instead)
//
// Each phase is a separate CS assertion of 16 SCLK edges.
// The CPU side loads tx_data and asserts tx_valid to trigger a TX phase.
// After RX completes, o_rx_data is valid and o_rx_done pulses.

module spi_slave (
  // RX: data received from master
  output wire [15:0] o_rx_data,
  output wire        o_rx_done,

  // TX: data to send to master (directly drives MISO shift register)
  input  wire [15:0] i_tx_data,
  input  wire        i_tx_load,  // pulse to load tx shift register

  // MISO output
  output wire        o_miso,

  // SPI bus
  input  wire        i_sclk,
  input  wire        i_mosi,
  input  wire        i_cs_n,

  // System
  input  wire        i_clk,
  input  wire        i_rst_n
);

  // =====================================================================
  // Synchronize SCLK into system clock domain (3-stage)
  // =====================================================================
  wire w_sclk_sync0, w_sclk_sync1, w_sclk_prev;

  dff sclk_ff0 (
    .o_Q(w_sclk_sync0), .o_Qn(),
    .i_D(i_sclk), .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  dff sclk_ff1 (
    .o_Q(w_sclk_sync1), .o_Qn(),
    .i_D(w_sclk_sync0), .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  dff sclk_ff2 (
    .o_Q(w_sclk_prev), .o_Qn(),
    .i_D(w_sclk_sync1), .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  wire w_sclk_rise = w_sclk_sync1 & ~w_sclk_prev;
  wire w_sclk_fall = ~w_sclk_sync1 & w_sclk_prev;

  // =====================================================================
  // Synchronize CS_n into system clock domain (3-stage, inversion trick)
  // DFFs reset to 0; we store ~i_cs_n (active-high) so reset gives
  // cs_active=0 → cs_n=1 (deasserted), matching behavioral reset-to-1.
  // =====================================================================
  wire w_cs_active0, w_cs_active1, w_cs_active_prev;

  dff cs_ff0 (
    .o_Q(w_cs_active0), .o_Qn(),
    .i_D(~i_cs_n), .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  dff cs_ff1 (
    .o_Q(w_cs_active1), .o_Qn(),
    .i_D(w_cs_active0), .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  dff cs_ff2 (
    .o_Q(w_cs_active_prev), .o_Qn(),
    .i_D(w_cs_active1), .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  wire w_cs_sync1 = ~w_cs_active1;

  // Edge detect (on the active-high domain)
  wire w_cs_rise = ~w_cs_active1 & w_cs_active_prev;
  wire w_cs_fall = w_cs_active1 & ~w_cs_active_prev;

  // =====================================================================
  // Synchronize MOSI (2-stage)
  // =====================================================================
  wire w_mosi_sync0, w_mosi_sync1;

  dff mosi_ff0 (
    .o_Q(w_mosi_sync0), .o_Qn(),
    .i_D(i_mosi), .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  dff mosi_ff1 (
    .o_Q(w_mosi_sync1), .o_Qn(),
    .i_D(w_mosi_sync0), .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

  // =====================================================================
  // TX shift register (MISO)
  // Load i_tx_data when i_tx_load; shift left on falling SCLK while CS
  // active; otherwise hold.
  // =====================================================================
  wire [15:0] w_tx_shift;
  wire        w_tx_en   = i_tx_load | (~w_cs_sync1 & w_sclk_fall);
  wire [15:0] w_tx_next = i_tx_load ? i_tx_data : {w_tx_shift[14:0], 1'b0};

  register #(.N(16)) tx_shift (
    .o_Q(w_tx_shift),
    .i_D(w_tx_next),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(w_tx_en)
  );

  // MISO drives MSB of TX shift register when CS is active
  assign o_miso = w_cs_sync1 ? 1'b0 : w_tx_shift[15];

  // =====================================================================
  // RX shift register (MOSI)
  // Shift in on rising SCLK while CS active; otherwise hold.
  // =====================================================================
  wire [15:0] w_rx_shift;
  wire        w_rx_en   = ~w_cs_sync1 & w_sclk_rise;
  wire [15:0] w_rx_next = {w_rx_shift[14:0], w_mosi_sync1};

  register #(.N(16)) rx_shift (
    .o_Q(w_rx_shift),
    .i_D(w_rx_next),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(w_rx_en)
  );

  // =====================================================================
  // Bit counter (5-bit)
  // Reset to 0 when CS deasserted; increment on rising SCLK while active.
  // =====================================================================
  wire [4:0] w_bit_cnt;
  wire       w_cnt_en   = w_cs_sync1 | w_sclk_rise;
  wire [4:0] w_cnt_next = w_cs_sync1 ? 5'd0 : (w_bit_cnt + 5'd1);

  register #(.N(5)) bit_cnt (
    .o_Q(w_bit_cnt),
    .i_D(w_cnt_next),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(w_cnt_en)
  );

  // =====================================================================
  // RX output latch + done pulse
  // Latch rx_shift into o_rx_data when CS rises and we received 16 bits.
  // o_rx_done pulses for one cycle (registered).
  // =====================================================================
  wire w_rx_latch = w_cs_rise & (w_bit_cnt == 5'd16);

  register #(.N(16)) rx_data (
    .o_Q(o_rx_data),
    .i_D(w_rx_shift),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(w_rx_latch)
  );

  dff done_ff (
    .o_Q(o_rx_done), .o_Qn(),
    .i_D(w_rx_latch), .i_clk(i_clk), .i_rst_n(i_rst_n), .i_en(1'b1)
  );

endmodule
