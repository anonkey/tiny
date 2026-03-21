module cpu(
   output [7:0]  o_pc,
   output [15:0] o_instr,
   output [7:0]  o_alu,
   input         i_clk,
   input         i_rst_n
);

   // --- Decoder outputs ---
   wire [3:0] w_alu_op;
   wire [2:0] w_rd, w_rs1, w_rs2;
   wire [7:0] w_imm8;
   wire [5:0] w_imm6;
   wire       w_reg_we, w_alu_src, w_pc_load, w_use_imm8;

   // --- FETCH: ROM addressed by PC ---
   wire [15:0] w_instr;
   assign o_instr = w_instr;

   rom #(.DEPTH(256), .WIDTH(16), .MEMFILE("program.hex")) imem (
      .o_data(w_instr),
      .i_addr(o_pc)
   );

   // --- DECODE ---
   decoder dec (
      .o_alu_op(w_alu_op),
      .o_rd(w_rd),
      .o_rs1(w_rs1),
      .o_rs2(w_rs2),
      .o_imm8(w_imm8),
      .o_imm6(w_imm6),
      .o_reg_we(w_reg_we),
      .o_alu_src(w_alu_src),
      .o_pc_load(w_pc_load),
      .o_use_imm8(w_use_imm8),
      .i_instr(w_instr)
   );

   // --- Register File ---
   wire [7:0] w_rd1_data, w_rd2_data;
   wire [7:0] w_write_data;

   regfile #(.NREG(8), .WIDTH(8)) rf (
      .o_rd1(w_rd1_data),
      .o_rd2(w_rd2_data),
      .i_wd(w_write_data),
      .i_raddr1(w_rs1),
      .i_raddr2(w_rs2),
      .i_waddr(w_rd),
      .i_we(w_reg_we),
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

   // --- EXECUTE: ALU ---
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

   // --- WRITEBACK: select what goes into rd ---
   // w_use_imm8=1 -> w_imm8, else -> w_alu_result
   wire [15:0] w_wb_mux_in;
   assign w_wb_mux_in = {w_imm8, w_alu_result};

   mux #(.WAY(2), .WIRE(8)) wb_sel (
      .i_in(w_wb_mux_in),
      .i_ctrl(w_use_imm8),
      .o_out(w_write_data)
   );

   // --- PC: jump on JMP or BEQ (when zero) ---
   wire w_beq;
   wire [3:0] w_opcode;
   assign w_opcode = w_instr[15:12];
   // BEQ = opcode 1100
   assign w_beq = w_opcode[3] & w_opcode[2] & ~w_opcode[1] & ~w_opcode[0];

   wire w_do_jump;
   assign w_do_jump = w_pc_load | (w_beq & w_zero_flag);

   pc pc_unit (
      .o_pc(o_pc),
      .i_load_addr(w_imm8),
      .i_load(w_do_jump),
      .i_en(1'b1),
      .i_clk(i_clk),
      .i_rst_n(i_rst_n)
   );

endmodule
