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

`timescale 1ns / 1ps

module tb_norflash();

reg sys_clk;
reg sys_rst;

reg [31:0] wb_adr_i;
wire [31:0] wb_dat_o;
reg wb_cyc_i;
reg wb_stb_i;
wire wb_ack_o;
reg [3:0] wb_sel_i;

wire [23:0] flash_adr;
wire [15:0] flash_d;
reg [15:0] flash_do;

always @(flash_adr) #110 flash_do <= flash_adr[15:0] + 16'b1;

norflash dut(
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),

	.wishbone_norflash_adr_i(wb_adr_i),
	.wishbone_norflash_dat_o(wb_dat_o),
	.wishbone_norflash_cyc_i(wb_cyc_i),
	.wishbone_norflash_stb_i(wb_stb_i),
	.wishbone_norflash_ack_o(wb_ack_o),
	.wishbone_norflash_sel_i(wb_sel_i),

	.norflash_adr(flash_adr),
	.norflash_d(flash_d),
	.norflash_oe_n(flash_oe_n),
	.norflash_we_n(flash_we_n)
);

//assign flash_d = flash_oe_n ? 16'bz : flash_do;
assign flash_d = flash_do;

task wbread;
	input [31:0] address;
	integer i;
	begin
		wb_adr_i <= address;
		wb_cyc_i <= 1'b1;
		wb_stb_i <= 1'b1;
		
		i = 1;
		while(~wb_ack_o) begin
			#5 sys_clk <= 1'b1;
			#5 sys_clk <= 1'b0;
			i = i + 1;
		end
		
		$display("Read address %h completed in %d cycles, result %h", address, i, wb_dat_o);
		
		wb_cyc_i <= 1'b0;
		wb_stb_i <= 1'b0;
		
		/* Let the core release its ack */
		#5 sys_clk <= 1'b1;
		#5 sys_clk <= 1'b0;
	end
endtask

initial begin
	$dumpfile("norflash.vcd");
	$dumpvars(1, dut);

	sys_rst <= 1'b1;
	sys_clk <= 1'b0;
	
	wb_adr_i <= 32'h00000000;
	wb_cyc_i <= 1'b0;
	wb_stb_i <= 1'b0;
	wb_sel_i <= 4'b1111;

	#5 sys_clk <= 1'b1;
	#5 sys_clk <= 1'b0;
	
	sys_rst <= 1'b0;
	#5 sys_clk <= 1'b1;
	#5 sys_clk <= 1'b0;
	
	wbread(32'h00000000);
	wbread(32'h00000004);

	wb_sel_i = 4'b0010;
	wbread(32'h0000fff1);

	wb_sel_i = 4'b0100;
	wbread(32'h0000fff2);

	wb_sel_i = 4'b1000;
	wbread(32'h0000fff3);

	wb_sel_i = 4'b0100;
	wbread(32'h0000fff0);

	wb_sel_i = 4'b1111;
	wbread(32'h00000010);
	#5 sys_clk = 1'b1;
	#5 sys_clk = 1'b0;
	#5 sys_clk = 1'b1;
	#5 sys_clk = 1'b0;
	wbread(32'h00000040);
	
	$finish;
end

endmodule
