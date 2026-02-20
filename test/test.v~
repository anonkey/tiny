module test_top;
   reg  [7:0] ui_in;
   wire [7:0] uo_out;

   reg  [7:0] uio_in;
   wire [7:0] uio_out;
   wire [7:0] uio_oe;

   reg	      ena;
   reg	      clk;
   reg	      rst_n;

   tt_um_top test_top(
		      .ui_in  (ui_in),    // Dedicated inputs
		      .uo_out (uo_out),   // Dedicated outputs

		      .uio_in (uio_in),   // IOs: Input path
		      .uio_out(uio_out),  // IOs: Output path
		      .uio_oe (uio_oe),   // IOs: Enable path (active high: 0=input, 1=output)

		      .ena    (ena),      // enable - goes high when design is selected
		      .clk    (clk),      // clock
		      .rst_n  (rst_n)     // not reset
		      );

   initial
     begin
	$dumpfile("signal_test_top.vcd");
        $dumpvars;
        $monitor("time %d\t clk %b\t ena %b\t ui_in %b\t uio_in %b\t uo_out %b\n", $time, clk, ena, ui_in, uio_in, uo_out);

	// Initial setup
	ui_in = 8'b0; uio_in = 8'b0; ena = 1'b0; clk = 1'b0; rst_n = 1'b0; #100;

	//kogge-stone - compacted
	$display("kogge-stone\n");
	ui_in <= 2; uio_in <= 5; #100;
	uio_in <= 128 + 5; #100;

	//onehalf_latch - compacted
	$display("onehalf_latch\n");
	ui_in <= 64 + 0; uio_in <= 1; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 0; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 1; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 1; uio_in <= 1; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 0; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 1; uio_in <= 1; #100;

	//twohalf_latch - compacted
	$display("two_half_latch\n");
	ui_in <= 64 + 0; uio_in <= 2; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 0; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 2; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 2; uio_in <= 2; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 0; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 2; uio_in <= 2; #100;

	//threehalf_latch - compacted
	$display("tree_half_latch\n");
	ui_in <= 64 + 0; uio_in <= 4; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 0; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 4; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 4; uio_in <= 4; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 0; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 4; uio_in <= 4; #100;

	//fourhalf_latch - compacted  
	$display("four_half_latch\n");
	ui_in <= 64 + 0; uio_in <= 8; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 0; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 8; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 8; uio_in <= 8; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 0; uio_in <= 0; #100;
	clk <= 1; #100; clk <= 0; ui_in <= 64 + 8; uio_in <= 8; #100;

	// VGA - ultra compacted
	$display("vga\n");
	ena <= 1; rst_n <= 1; clk <= 0; ui_in <= 128;
	repeat (100) begin clk <= 1; #100; clk <= 0; #100; end

	// CAM Tests - keep full functionality  
	$display("cam\n");
	rst_n <= 0; ena <= 1; clk <= 1; #100; clk <= 0; #100; rst_n <= 1;
	
	// Manual initialization of all CAM memory locations
	ui_in <= 192 + 32 + 0; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 1; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 2; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 3; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 4; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 5; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 6; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 7; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 8; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 9; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 10; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 11; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 12; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 13; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 14; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 15; uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	
	// Test 1: Write test values to specific locations
	$display("=== CAM: Writing test values ===");
	ui_in <= 192 + 32 + 0; uio_in <= 8'h55; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 1; uio_in <= 8'hAA; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 2; uio_in <= 8'h77; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 32 + 15; uio_in <= 8'h33; clk <= 1; #100; clk <= 0; #100;
	
	// Test 2: Search for written values
	$display("=== CAM: Searching values ===\n");
	ui_in <= 192 + 0; uio_in <= 8'h55; clk <= 1; #100; clk <= 0; #100;
	$display("Search 0x55: uo_out=%b (expected: found=1, addr=0)", uo_out);
	uio_in <= 8'hAA; clk <= 1; #100; clk <= 0; #100;
	$display("Search 0xAA: uo_out=%b (expected: found=1, addr=1)", uo_out);
	uio_in <= 8'h77; clk <= 1; #100; clk <= 0; #100;
	$display("Search 0x77: uo_out=%b (expected: found=1, addr=2)", uo_out);
	uio_in <= 8'h33; clk <= 1; #100; clk <= 0; #100;
	$display("Search 0x33: uo_out=%b (expected: found=1, addr=15)", uo_out);
	
	// Test 3: Search for non-existent value
	$display("=== CAM: Searching non-existent values ===");
	uio_in <= 8'hFF; clk <= 1; #100; clk <= 0; #100;
	$display("Search 0xFF: uo_out=%b (expected: found=0)", uo_out);
	uio_in <= 8'h00; clk <= 1; #100; clk <= 0; #100;
	$display("Search 0x00: uo_out=%b (expected: found=0)", uo_out);
	
	// Test 4: Overwrite existing value
	$display("=== CAM: Overwriting values ===\n");
	ui_in <= 192 + 32 + 1; uio_in <= 8'hCC; clk <= 0; #100; clk <= 1; #100; clk <= 0; #100;
	ui_in <= 192 + 0; uio_in <= 8'hAA; clk <= 1; #100; clk <= 0; #100;
	$display("Search old 0xAA: uo_out=%b (expected: found=0)", uo_out);
	uio_in <= 8'hCC; clk <= 1; #100; clk <= 0; #100;
	$display("Search new 0xCC: uo_out=%b (expected: found=1, addr=1)", uo_out);
	
	// Test 5: Reset functionality
	$display("=== CAM: Testing reset ===");
	rst_n <= 0; clk <= 1; #100; clk <= 0; #100; rst_n <= 1;
	ui_in <= 192 + 0; uio_in <= 8'hCC; clk <= 1; #100; clk <= 0; #100;
	$display("After reset, search 0xCC: uo_out=%b (expected: found=0)", uo_out);
	
	#100;
     end
endmodule // test_top
