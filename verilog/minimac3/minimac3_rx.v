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

module minimac3_rx(
	input phy_rx_clk,
	
	input [1:0] rx_ready,
	output [1:0] rx_done,
	output reg [10:0] rx_count_0,
	output reg [10:0] rx_count_1,
	
	output [7:0] rxb0_dat,
	output [10:0] rxb0_adr,
	output rxb0_we,
	output [7:0] rxb1_dat,
	output [10:0] rxb1_adr,
	output rxb1_we,
	
	input phy_dv,
	input [3:0] phy_rx_data,
	input phy_rx_er
);

reg [1:0] available_slots;
always @(posedge phy_rx_clk)
	available_slots <= (available_slots & ~rx_done) | rx_ready;
initial available_slots <= 2'd0;

reg [1:0] used_slot;
reg used_slot_update;
always @(posedge phy_rx_clk) begin
	if(used_slot_update) begin
		used_slot[0] <= available_slots[0];
		used_slot[1] <= available_slots[1] & ~available_slots[0];
	end
end

reg rx_done_ctl;
assign rx_done = {2{rx_done_ctl}} & used_slot;

reg rx_count_reset_ctl;
reg rx_count_inc_ctl;
wire [1:0] rx_count_reset = {2{rx_count_reset_ctl}} & used_slot;
wire [1:0] rx_count_inc = {2{rx_count_inc_ctl}} & used_slot;
always @(posedge phy_rx_clk) begin
	if(rx_count_reset[0])
		rx_count_0 <= 11'd0;
	else if(rx_count_inc[0])
		rx_count_0 <= rx_count_0 + 11'd1;
	if(rx_count_reset[1])
		rx_count_1 <= 11'd0;
	else if(rx_count_inc[1])
		rx_count_1 <= rx_count_1 + 11'd1;
end

assign rxb0_adr = rx_count_0;
assign rxb1_adr = rx_count_1;
reg rxb_we_ctl;
assign rxb0_we = rxb_we_ctl & used_slot[0];
assign rxb1_we = rxb_we_ctl & used_slot[1];

reg [3:0] lo;
reg [3:0] hi;
reg [1:0] load_nibble;
always @(posedge phy_rx_clk) begin
	if(load_nibble[0])
		lo <= phy_rx_data;
	if(load_nibble[1])
		hi <= phy_rx_data;
end
assign rxb0_dat = {hi, lo};
assign rxb1_dat = {hi, lo};

reg [1:0] state;
reg [1:0] next_state;

parameter IDLE		= 2'd0;
parameter LOAD_LO	= 2'd1;
parameter LOAD_HI	= 2'd2;
parameter TERMINATE	= 2'd3;

initial state <= IDLE;
always @(posedge phy_rx_clk)
	state <= next_state;

always @(*) begin
	used_slot_update = 1'b0;
	rx_done_ctl = 1'b0;
	rx_count_reset_ctl = 1'b0;
	rx_count_inc_ctl = 1'b0;
	rxb_we_ctl = 1'b0;
	load_nibble = 2'b00;
	
	next_state = state;
	case(state)
		IDLE: begin
			used_slot_update = 1'b1;
			if(phy_dv) begin
				rx_count_reset_ctl = 1'b1;
				used_slot_update = 1'b0;
				load_nibble = 2'b01;
				next_state = LOAD_HI;
			end
		end
		LOAD_LO: begin
			rxb_we_ctl = 1'b1;
			rx_count_inc_ctl = 1'b1;
			if(phy_dv) begin
				load_nibble = 2'b01;
				next_state = LOAD_HI;
			end else begin
				rx_done_ctl = 1'b1;
				next_state = TERMINATE;
			end
		end
		LOAD_HI: begin
			if(phy_dv) begin
				load_nibble = 2'b10;
				next_state = LOAD_LO;
			end else begin
				rx_done_ctl = 1'b1;
				next_state = TERMINATE;
			end
		end
		TERMINATE: begin
			used_slot_update = 1'b1;
			next_state = IDLE;
		end
	endcase
end

endmodule
