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

module minimac3_tx(
	input phy_tx_clk,

	input tx_start,
	output reg tx_done,
	input [10:0] tx_count,
	input [7:0] txb_dat,
	output [10:0] txb_adr,
	
	output reg phy_tx_en,
	output reg [3:0] phy_tx_data
);

reg phy_tx_en_r;
reg phy_tx_data_sel;
wire [3:0] phy_tx_data_r = phy_tx_data_sel ? txb_dat[7:4] : txb_dat[3:0];
always @(posedge phy_tx_clk) begin
	phy_tx_en <= phy_tx_en_r;
	phy_tx_data <= phy_tx_data_r;
end

reg [10:0] byte_count;
reg byte_count_reset;
reg byte_count_inc;
always @(posedge phy_tx_clk) begin
	if(byte_count_reset)
		byte_count <= 11'd0;
	else if(byte_count_inc)
		byte_count <= byte_count + 11'd1;
end
assign txb_adr = byte_count;
wire byte_count_max = byte_count == tx_count;

parameter IDLE		= 2'd0;
parameter SEND_LO	= 2'd1;
parameter SEND_HI	= 2'd2;
parameter TERMINATE	= 2'd3;

reg [1:0] state;
reg [1:0] next_state;

initial state <= IDLE;
always @(posedge phy_tx_clk)
	state <= next_state;

always @(*) begin
	phy_tx_en_r = 1'b0;
	phy_tx_data_sel = 1'b0;
	byte_count_reset = 1'b0;
	byte_count_inc = 1'b0;
	tx_done = 1'b0;
	
	next_state = state;
	
	case(state)
		IDLE: begin
			byte_count_reset = 1'b1;
			if(tx_start)
				next_state = SEND_LO;
		end
		SEND_LO: begin
			byte_count_inc = 1'b1;
			phy_tx_en_r = 1'b1;
			phy_tx_data_sel = 1'b0;
			next_state = SEND_HI;
		end
		SEND_HI: begin
			phy_tx_en_r = 1'b1;
			phy_tx_data_sel = 1'b1;
			if(byte_count_max)
				next_state = TERMINATE;
			else
				next_state = SEND_LO;
		end
		TERMINATE: begin
			byte_count_reset = 1'b1;
			tx_done = 1'b1;
			next_state = IDLE;
		end
	endcase
end

endmodule
