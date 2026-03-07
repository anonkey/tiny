/*
 * Copyright (c) 2024 jeremy alcim
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_jalcim (
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
   wire [7:0] pc_out;
   wire [15:0] instr_out;
   wire [7:0] alu_out;

   cpu cpu_inst (
      .pc_out(pc_out),
      .instr_out(instr_out),
      .alu_out(alu_out),
      .clk(clk),
      .rst_n(rst_n)
   );

   // uo_out = ALU result
   assign uo_out = alu_out;

   // uio_out = PC
   assign uio_out = pc_out;
   assign uio_oe  = 8'hFF;

   // Unused inputs
   wire _unused = &{ena, ui_in, uio_in};

endmodule
