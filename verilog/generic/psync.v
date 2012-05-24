module psync(
	input clk1,
	input i,
	input clk2,
	output o
);

reg level;
always @(posedge clk1)
	if(i)
		level <= ~level;

reg level1;
reg level2;
reg level3;
always @(posedge clk2) begin
	level1 <= level;
	level2 <= level1;
	level3 <= level2;
end

assign o = level2 ^ level3;

initial begin
	level <= 1'b0;
	level1 <= 1'b0;
	level2 <= 1'b0;
	level3 <= 1'b0;
end

endmodule
