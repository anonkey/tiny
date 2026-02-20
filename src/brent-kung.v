module black(P, G, Pi, Pj, Gi, Gj);
   output P,  G;
   input  Pi, Pj, Gi, Gj;

   assign P = Pi & Pj;
   assign G = Gi | (Pi & Gj);

endmodule

module grey(P, G, A, B);
   output P,  G;
   input  A, B;

   assign P = A ^ B;
   assign G = A & B;

endmodule

module green(C_out, Pi, Gi, C_in);
  output C_out;
  input Pi, Gi, C_in;

  assign C_out = Gi | (Pi & C_in);

endmodule

module stage_0(P, G, A, B);
   output [3:0] P, G;
   input [3:0]	A, B;

   grey grey_0(P[0], G[0], A[0], B[0]);
   grey grey_1(P[1], G[1], A[1], B[1]);
   grey grey_2(P[2], G[2], A[2], B[2]);
   grey grey_3(P[3], G[3], A[3], B[3]);

endmodule

module brent_kung_cin (output_S, input_A, input_B, Cin);
   output [7:0] output_S;
   input	Cin;
   input [5:0]	input_A, input_B;

   wire [3:0]	A, B;

   /* verilator lint_off UNUSEDSIGNAL */
   wire [1:0]	_ignored = {input_A[5] & input_B[5], input_A[4] & input_B[4]};
   assign A = input_A[3:0];
   assign B = input_B[3:0];

   wire [4:0]	out;
   assign output_S = {3'b0, out};

////////////////////////////////////////////////////////////

   wire [2:0]	black_P, black_G;
   wire [4:0]	C;

   wire	[3:0]	GREY_P, GREY_G;
   stage_0 stage_0_0(GREY_P, GREY_G, B, A);
   assign C[0] = Cin;

   assign out[0] = GREY_P[0] ^ C[0];

   //stage 1
   green green_1(C[1], GREY_P[0], GREY_G[0], C[0]);//0
   assign out[1] = GREY_P[1] ^ C[1];

//   wire [3:0] stage_1_P, stage_1_G;
   black black_0(black_P[0], black_G[0], GREY_P[1], GREY_P[0], GREY_G[1], GREY_G[0]);//1
   black black_1(black_P[1], black_G[1], GREY_P[3], GREY_P[2], GREY_G[3], GREY_G[2]);//3

   //stage 2
   green green_2(C[2], black_P[0], black_G[0], C[0]);//1
   assign out[2] = GREY_P[2] ^ C[2];

//   wire [3:0] stage_2_P, stage_2_G;
   black black_4(black_P[2], black_G[2], black_P[1], black_P[0], black_G[1], black_G[0]);//3

   //stage 3
   green green_3(C[3], GREY_P[2], GREY_G[2], C[2]);//2
   assign out[3] = GREY_P[3] ^ C[3];
   green green_4(C[4], black_P[2], black_G[2], C[0]);//3
   assign out[4] = C[4];

endmodule
/*

 `default_nettype none

module tt_um_brent_kung (
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
   //  assign uo_out  = ui_in + uio_in;  // Example: ou_out is the sum of ui_in and uio_in
   brent_kung_cin brent(uo_out[4:0], ui_in[3:0], uio_in[3:0], 1'b0);
   assign uio_out = 0;
   assign uio_oe  = 0;

   // List all unused inputs to prevent warnings
   wire _unused = &{ena, clk, rst_n, 1'b0, ui_in[7:4], uio_in[7:4]};
   assign uo_out[7:5] = 3'b0;

endmodule
*/
