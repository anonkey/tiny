`default_nettype none

// Half-CPU: PC + decoder + regfile + ALU, no internal memory.
// Instructions and data are fetched/stored over SPI via cpu_fsm + mem_ctrl.

module half_cpu (
  output [7:0]  o_pc,
  output [7:0]  o_alu,
  output [5:0]  o_state,          // {mem_state[2:0], cpu_state[2:0]}

  // SPI interface (directly exposed, spi_slave is in top.v)
  output [15:0] o_spi_tx_data,
  output        o_spi_tx_load,
  input  [15:0] i_spi_rx_data,
  input         i_spi_rx_done,

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

  // --- Debug state ---
  wire [2:0]  w_cpu_state;
  wire [2:0]  w_mem_state;
  assign o_state = {w_mem_state, w_cpu_state};

  // --- Instruction register (loaded from SPI RX by FSM) ---
  wire [15:0] w_instr;

  register #(.N(16)) instr_reg (
    .o_Q(w_instr),
    .i_D(i_spi_rx_data),
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
  wire [15:0] w_alu_b_mux_in;
  assign w_alu_b_mux_in = {{2{w_imm6[5]}}, w_imm6, w_rd2_data};

  mux #(.WAY(2), .WIRE(8)) alu_b_sel (
    .i_in(w_alu_b_mux_in),
    .i_ctrl(w_alu_src),
    .o_out(w_alu_b)
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
  assign w_zero_flag = ~|w_alu_result;

  // --- WRITEBACK mux: 3 sources ---
  // 00 = ALU result (R-type, ADDI)
  // 01 = imm8 (LDI)
  // 10 = SPI RX data low byte (LOAD)
  wire [7:0] w_load_data = i_spi_rx_data[7:0];

  wire [1:0] w_wb_sel;
  assign w_wb_sel = w_fsm_load_data_sel ? 2'd2 :
                    w_use_imm8          ? 2'd1 : 2'd0;

  wire [31:0] w_wb_mux_in;
  assign w_wb_mux_in = {8'h00, w_load_data, w_imm8, w_alu_result};

  mux #(.WAY(4), .WIRE(8)) wb_sel (
    .i_in(w_wb_mux_in),
    .i_ctrl(w_wb_sel),
    .o_out(w_write_data)
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
    .o_spi_tx_data(o_spi_tx_data),
    .o_spi_tx_load(o_spi_tx_load),
    .i_spi_rx_done(i_spi_rx_done),
    .i_mem_req(w_mem_req),
    .i_mem_op(w_mem_op),
    .i_mem_addr(w_mem_addr),
    .i_mem_wdata(w_mem_wdata),
    .o_mem_done(w_mem_done),
    .o_state(w_mem_state),
    .i_clk(i_clk),
    .i_rst_n(i_rst_n)
  );

endmodule
