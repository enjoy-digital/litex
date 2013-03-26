from fractions import Fraction

from migen.fhdl.structure import *
from migen.fhdl.specials import Instance
from migen.fhdl.module import Module

class M1CRG(Module):
	def __init__(self, pads, outfreq1x):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_sys2x_270 = ClockDomain()
		self.clock_domains.cd_sys4x_wr = ClockDomain()
		self.clock_domains.cd_sys4x_rd = ClockDomain()
		self.clock_domains.cd_eth_rx = ClockDomain()
		self.clock_domains.cd_eth_tx = ClockDomain()
		self.clock_domains.cd_vga = ClockDomain()

		self.clk4x_wr_strb = Signal()
		self.clk4x_rd_strb = Signal()

		###
		
		infreq = 50*1000000
		ratio = Fraction(outfreq1x)/Fraction(infreq)
		in_period = float(Fraction(1000000000)/Fraction(infreq))

		self.specials += Instance("m1crg",
			Instance.Parameter("in_period", in_period),
			Instance.Parameter("f_mult", ratio.numerator),
			Instance.Parameter("f_div", ratio.denominator),
			Instance.Input("clk50_pad", pads.clk50),
			Instance.Input("trigger_reset", pads.trigger_reset),
			
			Instance.Input("eth_rx_clk_pad", pads.eth_rx_clk),
			Instance.Input("eth_tx_clk_pad", pads.eth_tx_clk),
			
			Instance.Output("sys_clk", self.cd_sys.clk),
			Instance.Output("sys_rst", self.cd_sys.rst),
			Instance.Output("clk2x_270", self.cd_sys2x_270.clk),
			Instance.Output("clk4x_wr", self.cd_sys4x_wr.clk),
			Instance.Output("clk4x_rd", self.cd_sys4x_rd.clk),
			Instance.Output("eth_rx_clk", self.cd_eth_rx.clk),
			Instance.Output("eth_tx_clk", self.cd_eth_tx.clk),
			Instance.Output("vga_clk", self.cd_vga.clk),

			Instance.Output("clk4x_wr_strb", self.clk4x_wr_strb),
			Instance.Output("clk4x_rd_strb", self.clk4x_rd_strb),
			Instance.Output("norflash_rst_n", pads.norflash_rst_n),
			Instance.Output("ddr_clk_pad_p", pads.ddr_clk_p),
			Instance.Output("ddr_clk_pad_n", pads.ddr_clk_n),
			Instance.Output("eth_phy_clk_pad", pads.eth_phy_clk),
			Instance.Output("vga_clk_pad", pads.vga_clk))
