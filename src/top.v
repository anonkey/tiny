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

   // All output pins must be assigned. If not used, assign to 0.
   assign uio_out = 0;
   assign uio_oe  = 0;

   // List all unused inputs to prevent warnings
   wire _unused = &{ena, uio_in[6],
		    i_oh_p[5], i_oh_p[4], i_oh_n[5], i_oh_n[4],
		    &{_ignore1}, &{_ignore2}, &{_ignore3}};

   /* verilator lint_off UNUSEDSIGNAL */
   wire [5:0] _ignore1;
   /* verilator lint_off UNUSEDSIGNAL */
   wire [5:0] _ignore2;
   /* verilator lint_off UNUSEDSIGNAL */
   wire [5:0] _ignore3;

////////////////////////////////////////////////////////////

   //input demux
   wire [5:0] i_demux_1, i_demux_2;
   assign i_demux_1 = ui_in [5:0];
   assign i_demux_2 = uio_in[5:0];

   //ctrl demux/mux
   wire [1:0] ctrl;
   assign ctrl = ui_in[7:6];

   demux #(.WAY(4), .WIRE(6)) input_one (i_demux_1, ctrl, demux_output_1);
   demux #(.WAY(4), .WIRE(6)) input_two (i_demux_2, ctrl, demux_output_2);

   //output demux
   wire [23:0] demux_output_1, demux_output_2;
   assign {cam_instr, _ignore1, i_oh_p, i_brent_A} = demux_output_1;
   assign {_ignore2, _ignore3, i_oh_n, i_brent_B} = demux_output_2;

////////////////////////////////////////////////////////////

   //input mux
   wire [31:0] i_mux;
   assign i_mux = {output_cam, output_vga, o_oh, o_brent};

   mux #(.WAY(4), .WIRE(8)) ouput_one (i_mux, ctrl, uo_out);

////////////////////////////////////////////////////////////

   //brent-kung
   
   // input 6 bit
   wire [5:0] i_brent_A, i_brent_B;

   // input 1 bit
   wire	      i_brent_Cin;
   assign i_brent_Cin = uio_in[7];

   brent_kung_cin brent(o_brent, i_brent_A, i_brent_B, i_brent_Cin);

   //brent-kung output
   wire [7:0] o_brent;

////////////////////////////////////////////////////////////

   //onehalf_latch
   
   wire [5:0] i_oh_p, i_oh_n;

   onehalf_latch onehalt_latch(clk, i_oh_p[0], i_oh_n[0], o_oh[1], o_oh[0]);
   onehalf_latch twohalt_latch(clk, i_oh_p[1], i_oh_n[1], o_oh[3], o_oh[2]);
   onehalf_latch treehalt_latch(clk, i_oh_p[2], i_oh_n[2], o_oh[5], o_oh[4]);
   onehalf_latch fourhalt_latch(clk, i_oh_p[3], i_oh_n[3], o_oh[7], o_oh[6]);

   wire	[7:0] o_oh;

////////////////////////////////////////////////////////////

   vga_example vga(output_vga, clk, rst_n);
   wire [7:0] output_vga;

////////////////////////////////////////////////////////////

   wire [5:0] cam_instr;
   assign {cam_write, cam_addr} = cam_instr;

   wire	      cam_write;
   wire [4:0] cam_addr;
   wire [7:0] cam_data;

   assign cam_data = uio_in;
   cam cam(output_addr, found, clk, ena, rst_n, cam_write, cam_addr, cam_data);
   wire [4:0] output_addr;
   wire	      found;

   wire [7:0] output_cam;
   assign output_cam = {2'b0, found, output_addr};

endmodule
