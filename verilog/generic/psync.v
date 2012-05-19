/*
 * Milkymist SoC
 * Copyright (C) 2007, 2008, 2009, 2010, 2011 Sebastien Bourdeauducq
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
