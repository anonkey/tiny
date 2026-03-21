`default_nettype none

// Half-CPU: PC + decoder + regfile + ALU, no internal memory.
// Instructions and data are fetched/stored over SPI via cpu_fsm + mem_ctrl.
// Integrates spi_slave internally — only physical SPI wires are exposed.

module half_cpu (
  output [7:0]  o_pc,
  output [7:0]  o_alu,
  output [6:0]  o_state,          // {mem_state[3:0], cpu_state[2:0]}

  // Physical SPI bus (4 wires)
  output        o_mosi,
  input         i_miso,
  output        o_cs_n,
  input         i_sclk,

  input         i_clk,
  input         i_rst_n
);

  // --- FSM control signals ---
  wire        w_fsm_instr_en;
  wire        w_fsm_reg_we;
  wire        w_fsm_pc_en;
  wire        w_fsm_load_data_sel;

  // --- Memory bus (cpu_fsm <-> mem_ctrl) ---
  wire        w_mem_req;
  wire [1:0]  w_mem_op;
  wire [7:0]  w_mem_addr;
  wire [7:0]  w_mem_wdata;
  wire        w_mem_done;

  // --- Internal SPI signals (mem_ctrl <-> spi_slave) ---
  wire [7:0]  w_spi_tx_data;
  wire        w_spi_tx_load;
  wire [7:0]  w_spi_rx_data;
  wire        w_spi_byte_done;
  wire        w_cs_n;

  assign o_cs_n = w_cs_n;

  // --- Read data from mem_ctrl (accumulated RX bytes) ---
  wire [15:0] w_read_data;

  // --- Debug state ---
  wire [2:0]  w_cpu_state;
  wire [3:0]  w_mem_state;
  assign o_state = {w_mem_state, w_cpu_state};

  // --- Instruction register (loaded from mem_ctrl read data by FSM) ---
  wire [15:0] w_instr;

  register #(.N(16)) instr_reg (
    .o_Q(w_instr),
    .i_D(w_read_data),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n),
    .i_en(w_fsm_instr_en)
  );

  // --- DECODE ---
  wire [3:0] w_alu_op;
  wire [2:0] w_rd, w_rs1, w_rs2;
  wire [7:0] w_imm8;
  wire [5:0] w_imm6;
  wire       w_dec_reg_we, w_alu_src, w_pc_load, w_use_imm8;

  decoder dec (
    .o_alu_op(w_alu_op),
    .o_rd(w_rd),
    .o_rs1(w_rs1),
    .o_rs2(w_rs2),
    .o_imm8(w_imm8),
    .o_imm6(w_imm6),
    .o_reg_we(w_dec_reg_we),
    .o_alu_src(w_alu_src),
    .o_pc_load(w_pc_load),
    .o_use_imm8(w_use_imm8),
    .i_instr(w_instr)
  );

  // --- Derive LOAD/STORE/BEQ from opcode ---
  wire [3:0] w_opcode;
  assign w_opcode = w_instr[15:12];

  // LOAD = 1101, STORE = 1110, BEQ = 1100
  wire w_is_load  = w_opcode[3] & w_opcode[2] & ~w_opcode[1] & w_opcode[0];
  wire w_is_store = w_opcode[3] & w_opcode[2] & w_opcode[1] & ~w_opcode[0];
  wire w_is_beq   = w_opcode[3] & w_opcode[2] & ~w_opcode[1] & ~w_opcode[0];

  // --- Register File ---
  wire [7:0] w_rd1_data, w_rd2_data;
  wire [7:0] w_write_data;

  // Regfile write enable: FSM gate AND decoder permission
  wire w_reg_we_final = w_fsm_reg_we & w_dec_reg_we;

  regfile #(.NREG(8), .WIDTH(8)) rf (
    .o_rd1(w_rd1_data),
    .o_rd2(w_rd2_data),
    .i_wd(w_write_data),
    .i_raddr1(w_rs1),
    .i_raddr2(w_rs2),
    .i_waddr(w_rd),
    .i_we(w_reg_we_final),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  // --- ALU operand B: rs2 or sign-extended imm6 ---
  wire [7:0] w_alu_b;

  alu_operand_mux alu_b_sel (
    .o_alu_b(w_alu_b),
    .i_rs2_data(w_rd2_data),
    .i_imm6(w_imm6),
    .i_sel(w_alu_src),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  // --- ALU ---
  wire [7:0] w_alu_result;
  wire       w_alu_carry;
  assign o_alu = w_alu_result;

  alu alu_unit (
    .o_result(w_alu_result),
    .o_carry(w_alu_carry),
    .i_a(w_rd1_data),
    .i_b(w_alu_b),
    .i_opcode(w_alu_op)
  );

  // --- Zero flag for BEQ ---
  wire w_zero_flag;

  zero_flag #(.N(8)) zf (
    .o_zero(w_zero_flag),
    .i_data(w_alu_result)
  );

  // --- WRITEBACK mux: 3 sources ---
  writeback_mux wb (
    .o_write_data(w_write_data),
    .i_alu_result(w_alu_result),
    .i_imm8(w_imm8),
    .i_load_data(w_read_data[7:0]),
    .i_use_imm8(w_use_imm8),
    .i_load_data_sel(w_fsm_load_data_sel)
  );

  // --- PC ---
  wire w_do_jump;
  assign w_do_jump = w_pc_load | (w_is_beq & w_zero_flag);

  pc pc_unit (
    .o_pc(o_pc),
    .i_load_addr(w_imm8),
    .i_load(w_do_jump),
    .i_en(w_fsm_pc_en),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  // --- CPU FSM ---
  cpu_fsm fsm (
    .o_mem_req(w_mem_req),
    .o_mem_op(w_mem_op),
    .o_mem_addr(w_mem_addr),
    .o_mem_wdata(w_mem_wdata),
    .i_mem_done(w_mem_done),
    .o_instr_en(w_fsm_instr_en),
    .o_reg_we(w_fsm_reg_we),
    .o_pc_en(w_fsm_pc_en),
    .o_load_data_sel(w_fsm_load_data_sel),
    .o_state(w_cpu_state),
    .i_pc(o_pc),
    .i_alu_result(w_alu_result),
    .i_rs2_data(w_rd2_data),
    .i_is_load(w_is_load),
    .i_is_store(w_is_store),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  // --- Memory Controller ---
  mem_ctrl mctrl (
    .o_spi_tx_data(w_spi_tx_data),
    .o_spi_tx_load(w_spi_tx_load),
    .i_spi_rx_data(w_spi_rx_data),
    .i_spi_byte_done(w_spi_byte_done),
    .o_cs_n(w_cs_n),
    .o_read_data(w_read_data),
    .i_mem_req(w_mem_req),
    .i_mem_op(w_mem_op),
    .i_mem_addr(w_mem_addr),
    .i_mem_wdata(w_mem_wdata),
    .o_mem_done(w_mem_done),
    .o_state(w_mem_state),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

  // --- SPI Slave (shift register engine) ---
  spi_slave spi (
    .o_rx_data(w_spi_rx_data),
    .o_byte_done(w_spi_byte_done),
    .i_tx_data(w_spi_tx_data),
    .i_tx_load(w_spi_tx_load),
    .o_miso(o_mosi),      // our TX → MOSI on the bus (we are master)
    .i_sclk(i_sclk),
    .i_mosi(i_miso),      // bus MISO → our RX (we receive from slave)
    .i_cs_n(w_cs_n),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

endmodule
