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

module tb_conbus();

reg sys_rst;
reg sys_clk;

//------------------------------------------------------------------
// Wishbone master wires
//------------------------------------------------------------------
wire [31:0]	wishbone_m1_adr,
		wishbone_m2_adr;

wire [31:0]	wishbone_m1_dat_r,
		wishbone_m1_dat_w,
		wishbone_m2_dat_r,
		wishbone_m2_dat_w;

wire [3:0]	wishbone_m1_sel,
		wishbone_m2_sel;

wire		wishbone_m1_we,
		wishbone_m2_we;

wire		wishbone_m1_cyc,
		wishbone_m2_cyc;

wire		wishbone_m1_stb,
		wishbone_m2_stb;

wire		wishbone_m1_ack,
		wishbone_m2_ack;

//------------------------------------------------------------------
// Wishbone slave wires
//------------------------------------------------------------------
wire [31:0]	wishbone_s1_adr,
		wishbone_s2_adr;

wire [31:0]	wishbone_s1_dat_r,
		wishbone_s1_dat_w,
		wishbone_s2_dat_r,
		wishbone_s2_dat_w;

wire [3:0]	wishbone_s1_sel,
		wishbone_s2_sel;

wire		wishbone_s1_we,
		wishbone_s2_we;

wire		wishbone_s1_cyc,
		wishbone_s2_cyc;

wire		wishbone_s1_stb,
		wishbone_s2_stb;

wire		wishbone_s1_ack,
		wishbone_s2_ack;

//---------------------------------------------------------------------------
// Wishbone switch
//---------------------------------------------------------------------------
intercon dut(
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),

	// Master 0
	.wishbone_m1_dat_o(wishbone_m1_dat_w),
	.wishbone_m1_dat_i(wishbone_m1_dat_r),
	.wishbone_m1_adr_o(wishbone_m1_adr),
	.wishbone_m1_we_o(wishbone_m1_we),
	.wishbone_m1_sel_o(wishbone_m1_sel),
	.wishbone_m1_cyc_o(wishbone_m1_cyc),
	.wishbone_m1_stb_o(wishbone_m1_stb),
	.wishbone_m1_ack_i(wishbone_m1_ack),
	// Master 1
	.wishbone_m2_dat_o(wishbone_m2_dat_w),
	.wishbone_m2_dat_i(wishbone_m2_dat_r),
	.wishbone_m2_adr_o(wishbone_m2_adr),
	.wishbone_m2_we_o(wishbone_m2_we),
	.wishbone_m2_sel_o(wishbone_m2_sel),
	.wishbone_m2_cyc_o(wishbone_m2_cyc),
	.wishbone_m2_stb_o(wishbone_m2_stb),
	.wishbone_m2_ack_i(wishbone_m2_ack),

	// Slave 0
	.wishbone_s1_dat_o(wishbone_s1_dat_r),
	.wishbone_s1_dat_i(wishbone_s1_dat_w),
	.wishbone_s1_adr_i(wishbone_s1_adr),
	.wishbone_s1_sel_i(wishbone_s1_sel),
	.wishbone_s1_we_i(wishbone_s1_we),
	.wishbone_s1_cyc_i(wishbone_s1_cyc),
	.wishbone_s1_stb_i(wishbone_s1_stb),
	.wishbone_s1_ack_o(wishbone_s1_ack),
	// Slave 1
	.wishbone_s2_dat_o(wishbone_s2_dat_r),
	.wishbone_s2_dat_i(wishbone_s2_dat_w),
	.wishbone_s2_adr_i(wishbone_s2_adr),
	.wishbone_s2_sel_i(wishbone_s2_sel),
	.wishbone_s2_we_i(wishbone_s2_we),
	.wishbone_s2_cyc_i(wishbone_s2_cyc),
	.wishbone_s2_stb_i(wishbone_s2_stb),
	.wishbone_s2_ack_o(wishbone_s2_ack)
);

//---------------------------------------------------------------------------
// Masters
//---------------------------------------------------------------------------

wire wishbone_m1_end;
master #(
	.id(0)
) m0 (
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),
	
	.dat_w(wishbone_m1_dat_w),
	.dat_r(wishbone_m1_dat_r),
	.adr(wishbone_m1_adr),
	.we(wishbone_m1_we),
	.sel(wishbone_m1_sel),
	.cyc(wishbone_m1_cyc),
	.stb(wishbone_m1_stb),
	.ack(wishbone_m1_ack),
	
	.tend(wishbone_m1_end)
);

wire wishbone_m2_end;
master #(
	.id(1)
) m1 (
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),
	
	.dat_w(wishbone_m2_dat_w),
	.dat_r(wishbone_m2_dat_r),
	.adr(wishbone_m2_adr),
	.we(wishbone_m2_we),
	.sel(wishbone_m2_sel),
	.cyc(wishbone_m2_cyc),
	.stb(wishbone_m2_stb),
	.ack(wishbone_m2_ack),
	
	.tend(wishbone_m2_end)
);

//---------------------------------------------------------------------------
// Slaves
//---------------------------------------------------------------------------

slave #(
	.id(0)
) s0 (
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),

	.dat_w(wishbone_s1_dat_w),
	.dat_r(wishbone_s1_dat_r),
	.adr(wishbone_s1_adr),
	.we(wishbone_s1_we),
	.sel(wishbone_s1_sel),
	.cyc(wishbone_s1_cyc),
	.stb(wishbone_s1_stb),
	.ack(wishbone_s1_ack)
);

slave #(
	.id(1)
) s1 (
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),

	.dat_w(wishbone_s2_dat_w),
	.dat_r(wishbone_s2_dat_r),
	.adr(wishbone_s2_adr),
	.we(wishbone_s2_we),
	.sel(wishbone_s2_sel),
	.cyc(wishbone_s2_cyc),
	.stb(wishbone_s2_stb),
	.ack(wishbone_s2_ack)
);

initial sys_clk = 1'b0;
always #5 sys_clk = ~sys_clk;

wire all_end = wishbone_m1_end & wishbone_m2_end;

always begin
	$dumpfile("intercon.vcd");
	$dumpvars(1, dut);
	sys_rst = 1'b1;
	@(posedge sys_clk);
	#1 sys_rst = 1'b0;
	@(posedge all_end);
	$finish;
end

endmodule
