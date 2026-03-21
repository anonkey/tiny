/*
 * Copyright (c) 2024 theo seguier
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_anonkey (
		       input wire [7:0]	 ui_in,	  // Dedicated inputs
		       output wire [7:0] uo_out,  // Dedicated outputs

		       input wire [7:0]	 uio_in,  // IOs: Input path
		       output wire [7:0] uio_out, // IOs: Output path
		       output wire [7:0] uio_oe, // IOs: Enable path (active high: 0=input, 1=output)

		       input wire ena,	// always 1 when the design is powered, so you can ignore it
		       input wire clk,	// clock
		       input wire rst_n	// reset_n - low to reset
		      );

   // CPU outputs
   wire [7:0] w_pc;
   wire [15:0] w_instr;
   wire [7:0] w_alu;

   cpu cpu_inst (
      .o_pc(w_pc),
      .o_instr(w_instr),
      .o_alu(w_alu),
      .i_clk(clk),
      .i_rst_n(rst_n)
   );

   // uo_out = ALU result
   assign uo_out = w_alu;

   // uio_out = PC
   assign uio_out = 8'h00;
   assign uio_oe  = 8'h00;

   // Unused inputs
   wire w_unused = &{ena, ui_in, uio_in};

endmodule
