/*
 * This file is based on "Asynchronous FIFO" by Alex Claros F.,
 * itself based on the article "Asynchronous FIFO in Virtex-II FPGAs"
 * by Peter Alfke.
 */

module asfifo_graycounter #(
	parameter width = 2
) (
	output reg [width-1:0] gray_count,
	input ce,
	input rst,
	input clk
);

reg [width-1:0] binary_count;

always @(posedge clk, posedge rst) begin
	if(rst) begin
		binary_count <= {width{1'b0}} + 1;
		gray_count <= {width{1'b0}};
	end else if(ce) begin
		binary_count <= binary_count + 1;
		gray_count <= {binary_count[width-1],
				binary_count[width-2:0] ^ binary_count[width-1:1]};
	end
end

endmodule
