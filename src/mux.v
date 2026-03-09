module mux(input [SIZE_IN - 1:0] i_in,
	   input [SIZE_CTRL-1:0] i_ctrl,
	   output [WIRE-1:0]	 o_out);

   parameter WAY = 8;  // Nombre de voies par défaut
   parameter WIRE = 1; // taille de la sortie

   function integer log2;
    input integer i_value;
      begin
      i_value = i_value - 1;
      for (log2 = 0; i_value > 0; log2 = log2 + 1)
        i_value = i_value >> 1;
      end
   endfunction

   localparam SIZE_CTRL = log2(WAY);
   localparam SIZE_IN = WAY * WIRE;

   if (SIZE_CTRL == 1)
     /* verilator lint_off GENUNNAMED */
     assign o_out = i_ctrl ? i_in[2 * WIRE - 1 : WIRE] : i_in[WIRE - 1 : 0];
   else
     begin
	wire [WIRE-1:0]w_out1, w_out2;

	assign o_out = i_ctrl[SIZE_CTRL - 1] ? w_out2 : w_out1;
	mux #(.WAY(WAY/2), .WIRE(WIRE)) mux1(.i_in(i_in[(WAY/2) * WIRE - 1:0]),
					     .i_ctrl(i_ctrl[SIZE_CTRL - 2:0]),
					     .o_out(w_out1));

	mux #(.WAY(WAY/2), .WIRE(WIRE)) mux2(.i_in(i_in[SIZE_IN - 1 : (WAY/2) * WIRE]),
					     .i_ctrl(i_ctrl[SIZE_CTRL - 2:0]),
                                             .o_out(w_out2));

     end
endmodule

module demux(input [WIRE-1:0]	   i_in,
	     input [SIZE_CTRL-1:0] i_ctrl,
	     output [SIZE_OUT-1:0] o_out);

   parameter WAY = 8;   // Nombre de voies par défaut
   parameter WIRE = 1;  // Taille des sorties

   function integer log2;
    input integer i_value;
      begin
      i_value = i_value - 1;
      for (log2 = 0; i_value > 0; log2 = log2 + 1)
        i_value = i_value >> 1;
      end
   endfunction

   localparam SIZE_CTRL = log2(WAY);
   localparam SIZE_OUT  = WAY * WIRE;

   supply0 padding;

   if (SIZE_CTRL == 1)
     /* verilator lint_off GENUNNAMED */
     assign o_out = i_ctrl ? {i_in, {WIRE{padding}}} : {{WIRE{padding}}, i_in};
   else
     begin
        localparam N1 = (SIZE_OUT / 2) + (SIZE_OUT % 2);
        localparam N2 = SIZE_OUT / 2;

        wire [N1-1:0] w_w1;
        wire [N2-1:0] w_w2;

        assign o_out = i_ctrl[SIZE_CTRL-1] ? {w_w1, {N2{padding}}} : {{N1{padding}}, w_w2};
        demux #(.WAY(WAY/2), .WIRE(WIRE)) demux1(.i_in(i_in),
						 .i_ctrl(i_ctrl[SIZE_CTRL-2:0]),
      						 .o_out(w_w1));

        demux #(.WAY(WAY/2), .WIRE(WIRE)) demux2(.i_in(i_in),
						 .i_ctrl(i_ctrl[SIZE_CTRL-2:0]),
      						 .o_out(w_w2));
     end
endmodule
