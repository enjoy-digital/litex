module lm32_dp_ram(
	clk_i,
	rst_i,
	we_i,
	waddr_i,
	wdata_i,
	raddr_i,
	rdata_o);

parameter addr_width = 32;
parameter addr_depth = 1024;
parameter data_width = 8;

input clk_i;
input rst_i;
input we_i;
input [addr_width-1:0] waddr_i;
input [data_width-1:0] wdata_i;
input [addr_width-1:0] raddr_i;
output [data_width-1:0] rdata_o;

reg [data_width-1:0] ram[addr_depth-1:0];

reg [addr_width-1:0] raddr_r;
assign rdata_o = ram[raddr_r];

always @ (posedge clk_i)
begin
	if (we_i)
		ram[waddr_i] <= wdata_i;
	raddr_r <= raddr_i;
end

endmodule

