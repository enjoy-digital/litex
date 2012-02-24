`timescale 1ns / 1ps

module tb_s6ddrphy();

reg sys_clk = 1'b0;
reg clk2x_270 = 1'b0;
reg clk4x_wr = 1'b0;
wire clk4x_wr_strb;
wire clk4x_rd = clk4x_wr;
wire clk4x_rd_strb = clk4x_wr_strb;

initial begin
	while(1) begin
		sys_clk <= 1'b1;
		#6;
		sys_clk <= 1'b0;
		#6;
	end
end

initial begin
	#4.5;
	while(1) begin
		clk2x_270 <= 1'b1;
		#3;
		clk2x_270 <= 1'b0;
		#3;
	end
end

initial begin
	while(1) begin
		clk4x_wr <= 1'b1;
		#1.5;
		clk4x_wr <= 1'b0;
		#1.5;
	end
end

BUFPLL #(
	.DIVIDE(4)
) bufpll (
	.PLLIN(clk4x_wr),
	.GCLK(sys_clk),
	.LOCKED(1'b1),
	.IOCLK(),
	.LOCK(),
	.SERDESSTROBE(clk4x_wr_strb)
);

reg [12:0] dfi_address_p0 = 0;
reg [12:0] dfi_address_p1 = 0;

reg dfi_wrdata_en_p0 = 0;
reg [7:0] dfi_wrdata_mask_p0 = 0;
reg [63:0] dfi_wrdata_p0 = 0;
reg dfi_wrdata_en_p1 = 0;
reg [7:0] dfi_wrdata_mask_p1 = 0;
reg [63:0] dfi_wrdata_p1 = 0;

reg dfi_rddata_en_p0 = 0;
reg dfi_rddata_en_p1 = 0;

wire [31:0] sd_dq;
reg [31:0] dq_tb = 32'hzzzzzzzz;
assign sd_dq = dq_tb;

s6ddrphy #(
	.NUM_AD(13),
	.NUM_BA(2),
	.NUM_D(64)
) dut (
	.sys_clk(sys_clk),
	.clk2x_270(clk2x_270),
	.clk4x_wr(clk4x_wr),
	.clk4x_wr_strb(clk4x_wr_strb),
	.clk4x_rd(clk4x_rd),
	.clk4x_rd_strb(clk4x_rd_strb),
	
	.sd_clk_out_p(),
	.sd_clk_out_n(),
	
	.dfi_address_p0(dfi_address_p0),
	.dfi_address_p1(dfi_address_p1),
	.sd_a(),
	
	.dfi_wrdata_en_p0(dfi_wrdata_en_p0),
	.dfi_wrdata_mask_p0(dfi_wrdata_mask_p0),
	.dfi_wrdata_p0(dfi_wrdata_p0),
	.dfi_wrdata_en_p1(dfi_wrdata_en_p1),
	.dfi_wrdata_mask_p1(dfi_wrdata_mask_p1),
	.dfi_wrdata_p1(dfi_wrdata_p1),
	.sd_dq(sd_dq),
	.sd_dm(),
	.sd_dqs(),
	
	.dfi_rddata_en_p0(dfi_rddata_en_p0),
	.dfi_rddata_en_p1(dfi_rddata_en_p1),
	.dfi_rddata_w0(),
	.dfi_rddata_w1(),
	.dfi_rddata_valid_w0(),
	.dfi_rddata_valid_w1()
);

`define TEST_SIMPLE_CMD
`define TEST_WRITE
`define TEST_READ

initial begin
	$dumpfile("s6ddrphy.vcd");
	$dumpvars(3, dut);

`ifdef TEST_SIMPLE_CMD
	#13;
	dfi_address_p0 <= 13'h1aba;
	dfi_address_p1 <= 13'h1234;
	#12;
	dfi_address_p0 <= 0;
	dfi_address_p1 <= 0;
	#59;
`endif

`ifdef TEST_WRITE
	#13;
	dfi_address_p1 <= 13'h0dbe;
	dfi_wrdata_en_p1 <= 1;
	dfi_wrdata_mask_p0 <= 8'h12;
	dfi_wrdata_mask_p1 <= 8'h34;
	dfi_wrdata_p0 <= 64'hcafebabeabadface;
	dfi_wrdata_p1 <= 64'h0123456789abcdef;
	#12;
	dfi_address_p1 <= 0;
	dfi_wrdata_en_p1 <= 0;
	dfi_wrdata_mask_p0 <= 0;
	dfi_wrdata_mask_p1 <= 0;
	dfi_wrdata_p0 <= 64'd0;
	dfi_wrdata_p1 <= 64'd0;
	#59;
`endif

`ifdef TEST_READ
	#13;
	dfi_address_p0 <= 13'h1234;
	dfi_rddata_en_p0 <= 1;
	#12;
	dfi_address_p0 <= 0;
	dfi_rddata_en_p0 <= 0;
	#15.5;
	dq_tb <= 32'h12345678;
	#3;
	dq_tb <= 32'hdeadbeef;
	#3;
	dq_tb <= 32'hcafebabe;
	#3;
	dq_tb <= 32'habadface;
	#3;
	dq_tb <= 32'hzzzzzzzz;
	#60;
`endif
	
	$finish;
end

endmodule

module glbl();
wire GSR = 1'b0;
wire GTS = 1'b0;
endmodule
