/*
 * Milkymist SoC
 * Copyright (C) 2007, 2008, 2009, 2010, 2011, 2012 Sebastien Bourdeauducq
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

module minimac3_sync(
	input sys_clk,
	input phy_rx_clk,
	input phy_tx_clk,
	
	input [1:0] sys_rx_ready,
	output [1:0] sys_rx_done,
	output reg [10:0] sys_rx_count_0,
	output reg [10:0] sys_rx_count_1,
	
	input sys_tx_start,
	output sys_tx_done,
	input [10:0] sys_tx_count,
	
	output [1:0] phy_rx_ready,
	input [1:0] phy_rx_done,
	input [10:0] phy_rx_count_0,
	input [10:0] phy_rx_count_1,
	
	output phy_tx_start,
	input phy_tx_done,
	output reg [10:0] phy_tx_count
);

psync rx_ready_0(
	.clk1(sys_clk),
	.i(sys_rx_ready[0]),
	.clk2(phy_rx_clk),
	.o(phy_rx_ready[0])
);
psync rx_ready_1(
	.clk1(sys_clk),
	.i(sys_rx_ready[1]),
	.clk2(phy_rx_clk),
	.o(phy_rx_ready[1])
);
psync rx_done_0(
	.clk1(phy_rx_clk),
	.i(phy_rx_done[0]),
	.clk2(sys_clk),
	.o(sys_rx_done[0])
);
psync rx_done_1(
	.clk1(phy_rx_clk),
	.i(phy_rx_done[1]),
	.clk2(sys_clk),
	.o(sys_rx_done[1])
);
reg [10:0] sys_rx_count_0_r;
reg [10:0] sys_rx_count_1_r;
always @(posedge sys_clk) begin
	sys_rx_count_0_r <= phy_rx_count_0;
	sys_rx_count_0 <= sys_rx_count_0_r;
	sys_rx_count_1_r <= phy_rx_count_1;
	sys_rx_count_1 <= sys_rx_count_1_r;
end

psync tx_start(
	.clk1(sys_clk),
	.i(sys_tx_start),
	.clk2(phy_tx_clk),
	.o(phy_tx_start)
);
psync tx_done(
	.clk1(phy_tx_clk),
	.i(phy_tx_done),
	.clk2(sys_clk),
	.o(sys_tx_done)
);
reg [10:0] phy_tx_count_r;
always @(posedge phy_tx_clk) begin
	phy_tx_count_r <= sys_tx_count;
	phy_tx_count <= phy_tx_count_r;
end

endmodule
