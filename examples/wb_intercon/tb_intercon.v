/*
 * Milkymist SoC
 * Copyright (C) 2007, 2008, 2009, 2011, 2012 Sebastien Bourdeauducq
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
wire [29:0]	m1_wishbone_adr,
		m2_wishbone_adr;

wire [31:0]	m1_wishbone_dat_r,
		m1_wishbone_dat_w,
		m2_wishbone_dat_r,
		m2_wishbone_dat_w;

wire [3:0]	m1_wishbone_sel,
		m2_wishbone_sel;

wire		m1_wishbone_we,
		m2_wishbone_we;

wire		m1_wishbone_cyc,
		m2_wishbone_cyc;

wire		m1_wishbone_stb,
		m2_wishbone_stb;

wire		m1_wishbone_ack,
		m2_wishbone_ack;

//------------------------------------------------------------------
// Wishbone slave wires
//------------------------------------------------------------------
wire [29:0]	s1_wishbone_adr,
		s2_wishbone_adr;

wire [31:0]	s1_wishbone_dat_r,
		s1_wishbone_dat_w,
		s2_wishbone_dat_r,
		s2_wishbone_dat_w;

wire [3:0]	s1_wishbone_sel,
		s2_wishbone_sel;

wire		s1_wishbone_we,
		s2_wishbone_we;

wire		s1_wishbone_cyc,
		s2_wishbone_cyc;

wire		s1_wishbone_stb,
		s2_wishbone_stb;

wire		s1_wishbone_ack,
		s2_wishbone_ack;

//---------------------------------------------------------------------------
// Wishbone switch
//---------------------------------------------------------------------------
intercon dut(
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),

	// Master 0
	.m1_wishbone_dat_o(m1_wishbone_dat_w),
	.m1_wishbone_dat_i(m1_wishbone_dat_r),
	.m1_wishbone_adr_o(m1_wishbone_adr),
	.m1_wishbone_we_o(m1_wishbone_we),
	.m1_wishbone_sel_o(m1_wishbone_sel),
	.m1_wishbone_cyc_o(m1_wishbone_cyc),
	.m1_wishbone_stb_o(m1_wishbone_stb),
	.m1_wishbone_ack_i(m1_wishbone_ack),
	// Master 1
	.m2_wishbone_dat_o(m2_wishbone_dat_w),
	.m2_wishbone_dat_i(m2_wishbone_dat_r),
	.m2_wishbone_adr_o(m2_wishbone_adr),
	.m2_wishbone_we_o(m2_wishbone_we),
	.m2_wishbone_sel_o(m2_wishbone_sel),
	.m2_wishbone_cyc_o(m2_wishbone_cyc),
	.m2_wishbone_stb_o(m2_wishbone_stb),
	.m2_wishbone_ack_i(m2_wishbone_ack),

	// Slave 0
	.s1_wishbone_dat_o(s1_wishbone_dat_r),
	.s1_wishbone_dat_i(s1_wishbone_dat_w),
	.s1_wishbone_adr_i(s1_wishbone_adr),
	.s1_wishbone_sel_i(s1_wishbone_sel),
	.s1_wishbone_we_i(s1_wishbone_we),
	.s1_wishbone_cyc_i(s1_wishbone_cyc),
	.s1_wishbone_stb_i(s1_wishbone_stb),
	.s1_wishbone_ack_o(s1_wishbone_ack),
	// Slave 1
	.s2_wishbone_dat_o(s2_wishbone_dat_r),
	.s2_wishbone_dat_i(s2_wishbone_dat_w),
	.s2_wishbone_adr_i(s2_wishbone_adr),
	.s2_wishbone_sel_i(s2_wishbone_sel),
	.s2_wishbone_we_i(s2_wishbone_we),
	.s2_wishbone_cyc_i(s2_wishbone_cyc),
	.s2_wishbone_stb_i(s2_wishbone_stb),
	.s2_wishbone_ack_o(s2_wishbone_ack)
);

//---------------------------------------------------------------------------
// Masters
//---------------------------------------------------------------------------

wire m1_wishbone_end;
master #(
	.id(0)
) m0 (
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),
	
	.dat_w(m1_wishbone_dat_w),
	.dat_r(m1_wishbone_dat_r),
	.adr(m1_wishbone_adr),
	.we(m1_wishbone_we),
	.sel(m1_wishbone_sel),
	.cyc(m1_wishbone_cyc),
	.stb(m1_wishbone_stb),
	.ack(m1_wishbone_ack),
	
	.tend(m1_wishbone_end)
);

wire m2_wishbone_end;
master #(
	.id(1)
) m1 (
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),
	
	.dat_w(m2_wishbone_dat_w),
	.dat_r(m2_wishbone_dat_r),
	.adr(m2_wishbone_adr),
	.we(m2_wishbone_we),
	.sel(m2_wishbone_sel),
	.cyc(m2_wishbone_cyc),
	.stb(m2_wishbone_stb),
	.ack(m2_wishbone_ack),
	
	.tend(m2_wishbone_end)
);

//---------------------------------------------------------------------------
// Slaves
//---------------------------------------------------------------------------

slave #(
	.id(0)
) s0 (
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),

	.dat_w(s1_wishbone_dat_w),
	.dat_r(s1_wishbone_dat_r),
	.adr(s1_wishbone_adr),
	.we(s1_wishbone_we),
	.sel(s1_wishbone_sel),
	.cyc(s1_wishbone_cyc),
	.stb(s1_wishbone_stb),
	.ack(s1_wishbone_ack)
);

slave #(
	.id(1)
) s1 (
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),

	.dat_w(s2_wishbone_dat_w),
	.dat_r(s2_wishbone_dat_r),
	.adr(s2_wishbone_adr),
	.we(s2_wishbone_we),
	.sel(s2_wishbone_sel),
	.cyc(s2_wishbone_cyc),
	.stb(s2_wishbone_stb),
	.ack(s2_wishbone_ack)
);

initial sys_clk = 1'b0;
always #5 sys_clk = ~sys_clk;

wire all_end = m1_wishbone_end & m2_wishbone_end;

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
