module test_cam;
   reg clk, enable, rst_n, write;
   reg [4:0] addr;
   reg [7:0] data;

   wire [4:0] out;
   wire	      found;

   cam cam(out, found, clk, enable, rst_n, write, addr, data);

   initial
     begin
	$dumpfile("signal_test_top.vcd");
        $dumpvars;
        $monitor("time %d\t clk %b\t enable %b\t rst_n %b\t write %b\t addr %d\t data %d\t out %d\t found %b\n",
		 $time, clk, enable, rst_n, write, addr, data, out, found);

	// Initial state
	clk = 0;
	enable = 0;
	rst_n = 1;
	write = 0;
	addr = 0;
	data = 0;
	#100;

	// Reset sequence
	rst_n = 0;
	#100;
	rst_n = 1;
	#100;

	// Test 1: Write test values to specific locations  
	$display("=== Writing test values ===");
	write = 1;
	enable = 1;
	
	// Write unique test values to each address
	addr = 0; data = 8'h10; clk = 1; #10; clk = 0; #10;
	addr = 1; data = 8'h11; clk = 1; #10; clk = 0; #10;
	addr = 2; data = 8'h12; clk = 1; #10; clk = 0; #10;
	addr = 3; data = 8'h13; clk = 1; #10; clk = 0; #10;
	addr = 4; data = 8'h14; clk = 1; #10; clk = 0; #10;
	addr = 5; data = 8'h15; clk = 1; #10; clk = 0; #10;
	addr = 6; data = 8'h16; clk = 1; #10; clk = 0; #10;
	addr = 7; data = 8'h17; clk = 1; #10; clk = 0; #10;
	addr = 8; data = 8'h18; clk = 1; #10; clk = 0; #10;
	addr = 9; data = 8'h19; clk = 1; #10; clk = 0; #10;
	addr = 10; data = 8'h1A; clk = 1; #10; clk = 0; #10;
	addr = 11; data = 8'h1B; clk = 1; #10; clk = 0; #10;
	addr = 12; data = 8'h1C; clk = 1; #10; clk = 0; #10;
	addr = 13; data = 8'h1D; clk = 1; #10; clk = 0; #10;
	addr = 14; data = 8'h1E; clk = 1; #10; clk = 0; #10;
	addr = 15; data = 8'h1F; clk = 1; #10; clk = 0; #10;

	// Test 2: Search for all written values
	$display("=== Searching for all written values ===");
	write = 0;
	enable = 1;
	
	data = 8'h10; clk = 1; #10; clk = 0; #10; $display("Search 0x10: found=%b, addr=%d", found, out);
	data = 8'h11; clk = 1; #10; clk = 0; #10; $display("Search 0x11: found=%b, addr=%d", found, out);
	data = 8'h12; clk = 1; #10; clk = 0; #10; $display("Search 0x12: found=%b, addr=%d", found, out);
	data = 8'h13; clk = 1; #10; clk = 0; #10; $display("Search 0x13: found=%b, addr=%d", found, out);
	data = 8'h14; clk = 1; #10; clk = 0; #10; $display("Search 0x14: found=%b, addr=%d", found, out);
	data = 8'h15; clk = 1; #10; clk = 0; #10; $display("Search 0x15: found=%b, addr=%d", found, out);
	data = 8'h16; clk = 1; #10; clk = 0; #10; $display("Search 0x16: found=%b, addr=%d", found, out);
	data = 8'h17; clk = 1; #10; clk = 0; #10; $display("Search 0x17: found=%b, addr=%d", found, out);
	data = 8'h18; clk = 1; #10; clk = 0; #10; $display("Search 0x18: found=%b, addr=%d", found, out);
	data = 8'h19; clk = 1; #10; clk = 0; #10; $display("Search 0x19: found=%b, addr=%d", found, out);
	data = 8'h1A; clk = 1; #10; clk = 0; #10; $display("Search 0x1A: found=%b, addr=%d", found, out);
	data = 8'h1B; clk = 1; #10; clk = 0; #10; $display("Search 0x1B: found=%b, addr=%d", found, out);
	data = 8'h1C; clk = 1; #10; clk = 0; #10; $display("Search 0x1C: found=%b, addr=%d", found, out);
	data = 8'h1D; clk = 1; #10; clk = 0; #10; $display("Search 0x1D: found=%b, addr=%d", found, out);
	data = 8'h1E; clk = 1; #10; clk = 0; #10; $display("Search 0x1E: found=%b, addr=%d", found, out);
	data = 8'h1F; clk = 1; #10; clk = 0; #10; $display("Search 0x1F: found=%b, addr=%d", found, out);

	// Test 3: Search for non-existent values
	$display("=== Searching for non-existent values ===");
	data = 8'h00; clk = 1; #10; clk = 0; #10; $display("Search 0x00: found=%b, addr=%d", found, out);
	data = 8'hFF; clk = 1; #10; clk = 0; #10; $display("Search 0xFF: found=%b, addr=%d", found, out);
	data = 8'h55; clk = 1; #10; clk = 0; #10; $display("Search 0x55: found=%b, addr=%d", found, out);

	// Test 3: Write duplicate values and search
	$display("=== Testing duplicate values ===");
	write = 1;
	enable = 0;
	
	// Write same value to multiple locations
	addr = 0; data = 8'hAA; clk = 1; #10; clk = 0; #10;
	addr = 5; data = 8'hAA; clk = 1; #10; clk = 0; #10;
	addr = 10; data = 8'hAA; clk = 1; #10; clk = 0; #10;
	
	// Search for duplicate value (should find first occurrence)
	write = 0;
	enable = 1;
	data = 8'hAA; clk = 1; #10; clk = 0; #10; $display("Search 0xAA (duplicate): found=%b, addr=%d", found, out);

	// Test 4: Test reset functionality
	$display("=== Testing reset ===");
	rst_n = 0;
	clk = 1; #10; clk = 0; #10;
	rst_n = 1;
	
	// After reset, search should not find previous values
	enable = 1;
	data = 8'hAA; clk = 1; #10; clk = 0; #10; $display("After reset, search 0xAA: found=%b, addr=%d", found, out);

	#100;
	
     end
endmodule
