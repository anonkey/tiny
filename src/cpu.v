module cpu(
   pc_out, instr_out, alu_out,
   clk, rst_n
);

   output [7:0]  pc_out;
   output [15:0] instr_out;
   output [7:0]  alu_out;
   input         clk;
   input         rst_n;

   // --- Decoder outputs ---
   wire [3:0] alu_op;
   wire [2:0] rd, rs1, rs2;
   wire [7:0] imm8;
   wire [5:0] imm6;
   wire       reg_we, alu_src, pc_load, use_imm8;

   // --- FETCH: ROM addressed by PC ---
   wire [15:0] instr;
   assign instr_out = instr;

   rom #(.DEPTH(256), .WIDTH(16), .MEMFILE("program.hex")) imem (
      .data(instr),
      .addr(pc_out)
   );

   // --- DECODE ---
   decoder dec (
      .alu_op(alu_op),
      .rd(rd),
      .rs1(rs1),
      .rs2(rs2),
      .imm8(imm8),
      .imm6(imm6),
      .reg_we(reg_we),
      .alu_src(alu_src),
      .pc_load(pc_load),
      .use_imm8(use_imm8),
      .instr(instr)
   );

   // --- Register File ---
   wire [7:0] rd1_data, rd2_data;
   wire [7:0] write_data;

   regfile #(.NREG(8), .WIDTH(8)) rf (
      .rd1(rd1_data),
      .rd2(rd2_data),
      .wd(write_data),
      .raddr1(rs1),
      .raddr2(rs2),
      .waddr(rd),
      .we(reg_we),
      .clk(clk),
      .rst_n(rst_n)
   );

   // --- ALU operand B: rs2 or sign-extended imm6 ---
   wire [7:0] alu_b;
   wire [15:0] alu_b_mux_in;
   assign alu_b_mux_in = {{2{imm6[5]}}, imm6, rd2_data};

   mux #(.WAY(2), .WIRE(8)) alu_b_sel (
      .in(alu_b_mux_in),
      .ctrl(alu_src),
      .out(alu_b)
   );

   // --- EXECUTE: ALU ---
   wire [7:0] alu_result;
   wire       alu_carry;
   assign alu_out = alu_result;

   alu alu_unit (
      .result(alu_result),
      .carry(alu_carry),
      .a(rd1_data),
      .b(alu_b),
      .opcode(alu_op)
   );

   // --- Zero flag for BEQ ---
   wire zero_flag;
   assign zero_flag = ~|alu_result;

   // --- WRITEBACK: select what goes into rd ---
   // use_imm8=1 → imm8, else → alu_result
   wire [15:0] wb_mux_in;
   assign wb_mux_in = {imm8, alu_result};

   mux #(.WAY(2), .WIRE(8)) wb_sel (
      .in(wb_mux_in),
      .ctrl(use_imm8),
      .out(write_data)
   );

   // --- PC: jump on JMP or BEQ (when zero) ---
   wire beq;
   wire [3:0] opcode;
   assign opcode = instr[15:12];
   // BEQ = opcode 1100
   assign beq = opcode[3] & opcode[2] & ~opcode[1] & ~opcode[0];

   wire do_jump;
   assign do_jump = pc_load | (beq & zero_flag);

   pc pc_unit (
      .pc_out(pc_out),
      .load_addr(imm8),
      .load(do_jump),
      .clk(clk),
      .rst_n(rst_n)
   );

endmodule
