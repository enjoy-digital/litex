from fractions import Fraction

from migen.fhdl.structure import *

class M1CRG:
	def __init__(self, infreq, outfreq1x):
		self.clkin = Signal()
		self.trigger_reset = Signal()
		
		self.cd_sys = ClockDomain("sys")
		
		ratio = Fraction(outfreq1x)/Fraction(infreq)
		in_period = float(Fraction(1000000000)/Fraction(infreq))

		inst_items = [
			Instance.Parameter("in_period", in_period),
			Instance.Parameter("f_mult", ratio.numerator),
			Instance.Parameter("f_div", ratio.denominator),
			Instance.Input("clkin", self.clkin),
			Instance.Input("trigger_reset", self.trigger_reset),
			
			Instance.Output("sys_clk", self.cd_sys.clk),
			Instance.Output("sys_rst", self.cd_sys.rst)
		]
		
		for name in [
			"ac97_rst_n",
			"videoin_rst_n",
			"flash_rst_n",
			"clk2x_270",
			"clk4x_wr",
			"clk4x_wr_strb",
			"clk4x_rd",
			"clk4x_rd_strb",
			"phy_clk",
			"vga_clk",
			"vga_clk_pad"
		]:
			s = Signal(name=name)
			setattr(self, name, s)
			inst_items.append(Instance.Output(name, s))  
		
		self._inst = Instance("m1crg", *inst_items)


	def get_fragment(self):
		return Fragment(instances=[self._inst])
