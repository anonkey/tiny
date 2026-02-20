/* 
  Public Domain
  Lionel Sainte Cluque
  2025/10/14 rev alpha


This file implements the latch for a 1.5bit Digital to analog sigma delta modulator
It takes to input (from comparators) and output a 2 bit wide output to drive power stage.
As the two transistors can not be on at the same time the output can take three values only : 
  * 00
  * 01 
  * 10
But never 11


Reference : 
Design of a 3rd Order 1.5-Bit Continuous-Time Fully
Differential Sigma-Delta (Σ∆) Modulator Optimized for
a Class D Audio Amplifier Using Differential Pairs
Nuno Pereira, João Melo, Nuno Paulino
*/

module onehalf_latch(input  clk,
		     input in_p,
		     input in_n,

		     output out_p,
		     output out_n);

   reg reg_p, reg_n;
   wire	forbidden;

   always @(posedge clk)
     begin 
	reg_p <= in_p;
	reg_n <= in_n;
     end

   assign forbidden = ~(reg_p & reg_n);
   assign out_p = reg_p & forbidden;
   assign out_n = reg_n & forbidden;

endmodule
