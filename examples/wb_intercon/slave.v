/*
 * Milkymist SoC
 * Copyright (C) 2007, 2008, 2009, 2011 Sebastien Bourdeauducq
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

module slave #(
	parameter id = 0,
	parameter p = 3
) (
	input sys_clk,
	input sys_rst,
	
	input [31:0] dat_w,
	output reg [31:0] dat_r,
	input [29:0] adr,
	input we,
	input [3:0] sel,
	input cyc,
	input stb,
	output reg ack
);

always @(posedge sys_clk) begin
	if(sys_rst) begin
		dat_r <= 0;
		ack <= 0;
	end else begin
		if(cyc & stb & ~ack) begin
			if(($random % p) == 0) begin
				ack <= 1;
				if(~we)
					dat_r <= ($random << 16) + id;
				if(we)
					$display("[S%d] Ack W: %x:%x [%x]", id, adr, dat_w, sel);
				else
					$display("[S%d] Ack R: %x:%x [%x]", id, adr, dat_r, sel);
			end
		end else
			ack <= 0;
	end
end

endmodule
