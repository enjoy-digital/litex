from fractions import Fraction

from migen.fhdl.structure import *
from migen.fhdl.specials import Instance
from migen.fhdl.module import Module

class M1CRG(Module):
	def __init__(self, infreq, outfreq1x):
		self.clk50_pad = Signal()
		self.trigger_reset = Signal()
		
		self.eth_rx_clk_pad = Signal()
		self.eth_tx_clk_pad = Signal()
		
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_sys2x_270 = ClockDomain()
		self.clock_domains.cd_sys4x_wr = ClockDomain()
		self.clock_domains.cd_sys4x_rd = ClockDomain()
		self.clock_domains.cd_eth_rx = ClockDomain()
		self.clock_domains.cd_eth_tx = ClockDomain()
		self.clock_domains.cd_vga = ClockDomain()
		
		ratio = Fraction(outfreq1x)/Fraction(infreq)
		in_period = float(Fraction(1000000000)/Fraction(infreq))

		inst_items = [
			Instance.Parameter("in_period", in_period),
			Instance.Parameter("f_mult", ratio.numerator),
			Instance.Parameter("f_div", ratio.denominator),
			Instance.Input("clk50_pad", self.clk50_pad),
			Instance.Input("trigger_reset", self.trigger_reset),
			
			Instance.Input("eth_rx_clk_pad", self.eth_rx_clk_pad),
			Instance.Input("eth_tx_clk_pad", self.eth_tx_clk_pad),
			
			Instance.Output("sys_clk", self.cd_sys.clk),
			Instance.Output("sys_rst", self.cd_sys.rst),
			Instance.Output("clk2x_270", self.cd_sys2x_270.clk),
			Instance.Output("clk4x_wr", self.cd_sys4x_wr.clk),
			Instance.Output("clk4x_rd", self.cd_sys4x_rd.clk),
			Instance.Output("eth_rx_clk", self.cd_eth_rx.clk),
			Instance.Output("eth_tx_clk", self.cd_eth_tx.clk),
			Instance.Output("vga_clk", self.cd_vga.clk)
		]
		
		for name in [
			"norflash_rst_n",
			"clk4x_wr_strb",
			"clk4x_rd_strb",
			"ddr_clk_pad_p",
			"ddr_clk_pad_n",
			"eth_phy_clk_pad",
			"vga_clk_pad"
		]:
			s = Signal(name=name)
			setattr(self, name, s)
			inst_items.append(Instance.Output(name, s))  
		
		self.specials += Instance("m1crg", *inst_items)
