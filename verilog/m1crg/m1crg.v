/*
 * Milkymist-NG SoC
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

module m1crg #(
	parameter in_period = 0.0,
	parameter f_mult = 0,
	parameter f_div = 0,
	parameter clk2x_period = (in_period*f_div)/(2.0*f_mult)
) (
	input clkin,
	input trigger_reset,
	
	output sys_clk,
	output reg sys_rst,
	
	/* Reset off-chip devices */
	output ac97_rst_n,
	output videoin_rst_n,
	output flash_rst_n,
	
	/* DDR PHY clocks and reset */
	output clk2x_90,
	output clk4x_wr_left,
	output clk4x_wr_strb_left,
	output clk4x_wr_right,
	output clk4x_wr_strb_right,
	output clk4x_rd_left,
	output clk4x_rd_strb_left,
	output clk4x_rd_right,
	output clk4x_rd_strb_right,
	inout rd_clk_lb /* < unconnected clock pin for read clock PLL loopback */
);

/*
 * Reset
 */

wire reset_n;

reg [19:0] rst_debounce;
always @(posedge sys_clk, negedge reset_n) begin
	if(~reset_n) begin
		rst_debounce <= 20'hFFFFF;
		sys_rst <= 1'b1;
	end else begin
		if(trigger_reset)
			rst_debounce <= 20'hFFFFF;
		else if(rst_debounce != 20'd0)
			rst_debounce <= rst_debounce - 20'd1;
		sys_rst <= rst_debounce != 20'd0;
	end
end

assign ac97_rst_n = ~sys_rst;
assign videoin_rst_n = ~sys_rst;

/*
 * We must release the Flash reset before the system reset
 * because the Flash needs some time to come out of reset
 * and the CPU begins fetching instructions from it
 * as soon as the system reset is released.
 * From datasheet, minimum reset pulse width is 100ns
 * and reset-to-read time is 150ns.
 */

reg [7:0] flash_rstcounter;

always @(posedge sys_clk, negedge reset_n) begin
	if(~reset_n) begin
		flash_rstcounter <= 8'd0;
	end else begin
		if(trigger_reset)
			flash_rstcounter <= 8'd0;
		else if(~flash_rstcounter[7])
			flash_rstcounter <= flash_rstcounter + 8'd1;
	end
end

assign flash_rst_n = flash_rstcounter[7];

/*
 * Clock management. Largely taken from the NWL reference design.
 */
 
wire sdr_clkin;
wire clkdiv;

IBUF #(
	.IOSTANDARD("DEFAULT")
) clk2_iob (
	.I(clkin),
	.O(sdr_clkin)
);

BUFIO2 #(
	.DIVIDE(1),
	.DIVIDE_BYPASS("FALSE"),
	.I_INVERT("FALSE")
) bufio2_inst2 (
	.I(sdr_clkin),
	.IOCLK(),
	.DIVCLK(clkdiv),
	.SERDESSTROBE()
);

wire pll1_lckd;
wire buf_pll1_fb_out;
wire pll1out0;
wire pll1out1;
wire pll1out2;
wire pll1out3;

PLL_ADV #(
	.BANDWIDTH("OPTIMIZED"),
	.CLKFBOUT_MULT(4*f_mult),
	.CLKFBOUT_PHASE(0.0),
	.CLKIN1_PERIOD(in_period),
	.CLKIN2_PERIOD(in_period),
	.CLKOUT0_DIVIDE(f_div),
	.CLKOUT0_DUTY_CYCLE(0.5),
	.CLKOUT0_PHASE(0),
	.CLKOUT1_DIVIDE(f_div),
	.CLKOUT1_DUTY_CYCLE(0.5),
	.CLKOUT1_PHASE(0),
	.CLKOUT2_DIVIDE(4*f_div),
	.CLKOUT2_DUTY_CYCLE(0.5),
	.CLKOUT2_PHASE(0.0),
	.CLKOUT3_DIVIDE(2*f_div),
	.CLKOUT3_DUTY_CYCLE(0.5),
	.CLKOUT3_PHASE(90),
	.CLKOUT4_DIVIDE(7),
	.CLKOUT4_DUTY_CYCLE(0.5),
	.CLKOUT4_PHASE(0),
	.CLKOUT5_DIVIDE(7),
	.CLKOUT5_DUTY_CYCLE(0.5),
	.CLKOUT5_PHASE(0.0),
	.COMPENSATION("INTERNAL"),
	.DIVCLK_DIVIDE(1),
	.REF_JITTER(0.100),
	.CLK_FEEDBACK("CLKFBOUT"),
	.SIM_DEVICE("SPARTAN6")
) pll1 (
	.CLKFBDCM(),
	.CLKFBOUT(buf_pll1_fb_out),
	.CLKOUT0(pll1out0), /* < x4 180 clock for transmitter */
	.CLKOUT1(pll1out1), /* < x4 180 clock for transmitter */
	.CLKOUT2(pll1out2), /* < x1 clock for memory controller */
	.CLKOUT3(pll1out3), /* < x2 90 clock to generate memory clock, clock DQS and memory address and control signals. */
	.CLKOUT4(),
	.CLKOUT5(),
	.CLKOUTDCM0(),
	.CLKOUTDCM1(),
	.CLKOUTDCM2(),
	.CLKOUTDCM3(),
	.CLKOUTDCM4(),
	.CLKOUTDCM5(),
	.DO(),
	.DRDY(),
	.LOCKED(pll1_lckd),
	.CLKFBIN(buf_pll1_fb_out),
	.CLKIN1(clkdiv),
	.CLKIN2(1'b0),
	.CLKINSEL(1'b1),
	.DADDR(5'b00000),
	.DCLK(1'b0),
	.DEN(1'b0),
	.DI(16'h0000),
	.DWE(1'b0),
	.RST(1'b0),
	.REL(1'b0)
);

BUFPLL #(
	.DIVIDE(4)
) wr_bufpll_left (
	.PLLIN(pll1out0),
	.GCLK(sys_clk),
	.LOCKED(pll1_lckd),
	.IOCLK(clk4x_wr_left),
	.LOCK(),
	.SERDESSTROBE(clk4x_wr_strb_left)
);

BUFPLL #(
	.DIVIDE(4)
) wr_bufpll_right (
	.PLLIN(pll1out1),
	.GCLK(sys_clk),
	.LOCKED(pll1_lckd),
	.IOCLK(clk4x_wr_right),
	.LOCK(),
	.SERDESSTROBE(clk4x_wr_strb_right)
);

BUFG bufg_x1(
	.I(pll1out2),
	.O(sys_clk)
);

BUFG bufg_x2_2(
	.I(pll1out3),
	.O(clk2x_90)
);

/*
 * Generate clk4x_rd. This clock is sourced from clk2x_90.
 * An IODELAY2 element is included in the path of this clock so that 
 * any variation in IDELAY element's base delay is compensated when this clock 
 * is used to capture read data which also goes through IDELAY element.
 */

wire rd_clk_out;

ODDR2 #(
	.DDR_ALIGNMENT("C0"),
	.INIT(1'b0),
	.SRTYPE("ASYNC")
) rd_clk_out_inst (
	.Q(rd_clk_out),
	.C0(clk2x_90),
	.C1(~clk2x_90),
	.CE(1'b1),
	.D0(1'b1),
	.D1(1'b0),
	.R(1'b0),
	.S(1'b0)
);

wire rd_clk_out_oe_n;

ODDR2 #(
	.DDR_ALIGNMENT("C0"),
	.INIT(1'b0),
	.SRTYPE("ASYNC")
) rd_clk_out_oe_inst (
	.Q(rd_clk_out_oe_n),
	.C0(clk2x_90),
	.C1(~clk2x_90),
	.CE(1'b1),
	.D0(1'b0),
	.D1(1'b0),
	.R(1'b0),
	.S(1'b0)
);

wire rd_clk_fb;

/* Dummy pin used for calibration */
IOBUF rd_clk_loop_back_inst(
	.O(rd_clk_fb),
	.IO(rd_clk_lb),
	.I(rd_clk_out),
	.T(rd_clk_out_oe_n)
);

wire rd_clk_fb_dly;

IODELAY2 #(
	.DATA_RATE("DDR"),
	.IDELAY_VALUE(0),
	.IDELAY2_VALUE(0),
	.IDELAY_MODE("NORMAL"),
	.ODELAY_VALUE(0),
	.IDELAY_TYPE("FIXED"),
	.COUNTER_WRAPAROUND("STAY_AT_LIMIT"),
	.DELAY_SRC("IDATAIN"),
	.SERDES_MODE("NONE"),
	.SIM_TAPDELAY_VALUE(49)
) iodelay_cm (
	.IDATAIN(rd_clk_fb),
	.TOUT(),
	.DOUT(),
	.T(1'b1),
	.ODATAIN(1'b0),
	.DATAOUT(rd_clk_fb_dly),
	.DATAOUT2(),
	.IOCLK0(1'b0),
	.IOCLK1(1'b0),
	.CLK(1'b0),
	.CAL(1'b0),
	.INC(1'b0),
	.CE(1'b0),
	.RST(1'b0),
	.BUSY()
);

wire rd_clk_fb_dly_bufio;

BUFIO2 #(
	.DIVIDE(1),
	.DIVIDE_BYPASS("FALSE"),
	.I_INVERT("FALSE")
) bufio2_inst (
	.I(rd_clk_fb_dly),
	.IOCLK(),
	.DIVCLK(rd_clk_fb_dly_bufio),
	.SERDESSTROBE()
);

wire pll2_lckd;
wire buf_pll2_fb_out;
wire pll2out0;
wire pll2out1;

PLL_ADV #(
	.BANDWIDTH("OPTIMIZED"),
	.CLKFBOUT_MULT(4),
	.CLKFBOUT_PHASE(0.0),
	.CLKIN1_PERIOD(clk2x_period),
	.CLKIN2_PERIOD(clk2x_period),
	.CLKOUT0_DIVIDE(2),
	.CLKOUT0_DUTY_CYCLE(0.5),
	.CLKOUT0_PHASE(0.0),
	.CLKOUT1_DIVIDE(2),
	.CLKOUT1_DUTY_CYCLE(0.5),
	.CLKOUT1_PHASE(0.0),
	.CLKOUT2_DIVIDE(7),
	.CLKOUT2_DUTY_CYCLE(0.5),
	.CLKOUT2_PHASE(0.0),
	.CLKOUT3_DIVIDE(7),
	.CLKOUT3_DUTY_CYCLE(0.5),
	.CLKOUT3_PHASE(0.0),
	.CLKOUT4_DIVIDE(7),
	.CLKOUT4_DUTY_CYCLE(0.5),
	.CLKOUT4_PHASE(0.0),
	.CLKOUT5_DIVIDE(7),
	.CLKOUT5_DUTY_CYCLE (0.5),
	.CLKOUT5_PHASE(0.0),
	.COMPENSATION("INTERNAL"),
	.DIVCLK_DIVIDE(1),
	.REF_JITTER(0.100),
	.CLK_FEEDBACK("CLKFBOUT"),
	.SIM_DEVICE("SPARTAN6")
) pll2 (
	.CLKFBDCM(),
	.CLKFBOUT(buf_pll2_fb_out),
	.CLKOUT0(pll2out0), /* < x4 clock to capture read data */
	.CLKOUT1(pll2out1), /* < x4 clock to capture read data */
	.CLKOUT2(),
	.CLKOUT3(),
	.CLKOUT4(),
	.CLKOUT5(),
	.CLKOUTDCM0(),
	.CLKOUTDCM1(),
	.CLKOUTDCM2(),
	.CLKOUTDCM3(),
	.CLKOUTDCM4(),
	.CLKOUTDCM5(),
	.DO(),
	.DRDY(),
	.LOCKED(pll2_lckd),
	.CLKFBIN(buf_pll2_fb_out),
	.CLKIN1(rd_clk_fb_dly_bufio),
	.CLKIN2(1'b0),
	.CLKINSEL(1'b1),
	.DADDR(5'b00000),
	.DCLK(1'b0),
	.DEN(1'b0),
	.DI(16'h0000),
	.DWE(1'b0),
	.RST(~pll1_lckd),
	.REL(1'b0)
);

BUFPLL #(
	.DIVIDE(4)
) rd_bufpll_left (
	.PLLIN(pll2out0),
	.GCLK(sys_clk),
	.LOCKED(pll2_lckd),
	.IOCLK(clk4x_rd_left),
	.LOCK(),
	.SERDESSTROBE(clk4x_rd_strb_left)
);

BUFPLL #(
	.DIVIDE(4)
) rd_bufpll_right (
	.PLLIN(pll2out1),
	.GCLK(sys_clk),
	.LOCKED(pll2_lckd),
	.IOCLK(clk4x_rd_right),
	.LOCK(),
	.SERDESSTROBE(clk4x_rd_strb_right)
);

wire sdram_sys_clk_lock_d16;
reg sdram_sys_clk_lock_d17;

/*
 * Async reset generation
 * The reset is de-asserted 16 clocks after both internal clocks are locked.
 */

SRL16 reset_delay_sr(
	.CLK(sys_clk),
	.D(pll1_lckd & pll2_lckd),
	.A0(1'b1),
	.A1(1'b1),
	.A2(1'b1),
	.A3(1'b1),
	.Q(sdram_sys_clk_lock_d16)
);

always @(posedge sys_clk)
	sdram_sys_clk_lock_d17 <= sdram_sys_clk_lock_d16;

assign reset_n = sdram_sys_clk_lock_d17;
 
endmodule
