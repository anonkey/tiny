module mux(input [SIZE_IN - 1:0] in,
	   input [SIZE_CTRL-1:0] ctrl,
	   output [WIRE-1:0]	 out);

   parameter WAY = 8;  // Nombre de voies par défaut
   parameter WIRE = 1; // taille de la sortie

   function integer log2;
      input integer value;
      begin
         value = value - 1;
         for (log2 = 0; value > 0; log2 = log2 + 1)
           value = value >> 1;
      end
   endfunction

   localparam SIZE_CTRL = log2(WAY);
   localparam SIZE_IN = WAY * WIRE;

   if (SIZE_CTRL == 1)
     /* verilator lint_off GENUNNAMED */
     assign out = ctrl ? in[2 * WIRE - 1 : WIRE] : in[WIRE - 1 : 0];
   else
     begin
	wire [WIRE-1:0]out1, out2;

	assign out = ctrl[SIZE_CTRL - 1] ? out2 : out1;
	mux #(.WAY(WAY/2), .WIRE(WIRE)) mux1(.in(in[(WAY/2) * WIRE - 1:0]),
					     .ctrl(ctrl[SIZE_CTRL - 2:0]),
					     .out(out1));

	mux #(.WAY(WAY/2), .WIRE(WIRE)) mux2(.in(in[SIZE_IN - 1 : (WAY/2) * WIRE]),
					     .ctrl(ctrl[SIZE_CTRL - 2:0]),
                                             .out(out2));

     end
endmodule

module demux(input [WIRE-1:0]	   in,
	     input [SIZE_CTRL-1:0] ctrl,
	     output [SIZE_OUT-1:0] out);

   parameter WAY = 8;   // Nombre de voies par défaut
   parameter WIRE = 1;  // Taille des sorties

   function integer log2;
      input integer value;
      begin
         value = value - 1;
         for (log2 = 0; value > 0; log2 = log2 + 1)
           value = value >> 1;
      end
   endfunction

   localparam SIZE_CTRL = log2(WAY);
   localparam SIZE_OUT  = WAY * WIRE;

   supply0 padding;

   if (SIZE_CTRL == 1)
     /* verilator lint_off GENUNNAMED */
     assign out = ctrl ? {in, {WIRE{padding}}} : {{WIRE{padding}}, in};
   else
     begin
        localparam N1 = (SIZE_OUT / 2) + (SIZE_OUT % 2);
        localparam N2 = SIZE_OUT / 2;

        wire [N1-1:0] W1;
        wire [N2-1:0] W2;

        assign out = ctrl[SIZE_CTRL-1] ? {W1, {N2{padding}}} : {{N1{padding}}, W2};
        demux #(.WAY(WAY/2), .WIRE(WIRE)) demux1(.in(in),
						 .ctrl(ctrl[SIZE_CTRL-2:0]),
						 .out(W1));

        demux #(.WAY(WAY/2), .WIRE(WIRE)) demux2(.in(in),
						 .ctrl(ctrl[SIZE_CTRL-2:0]),
						 .out(W2));
     end
endmodule
