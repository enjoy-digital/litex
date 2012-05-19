from fractions import Fraction

from migen.fhdl.structure import *

class M1CRG:
	def __init__(self, infreq, outfreq1x):
		self.clkin = Signal()
		self.trigger_reset = Signal()
		
		generated = []
		for name in [
			"sys_clk",
			"sys_rst",
			"ac97_rst_n",
			"videoin_rst_n",
			"flash_rst_n",
			"clk2x_270",
			"clk4x_wr",
			"clk4x_wr_strb",
			"clk4x_rd",
			"clk4x_rd_strb",
			"phy_clk"
		]:
			s = Signal(name=name)
			setattr(self, name, s)
			generated.append((name, s))  
		
		ratio = Fraction(outfreq1x)/Fraction(infreq)
		in_period = float(Fraction(1000000000)/Fraction(infreq))
		
		self._inst = Instance("m1crg",
			generated,
			[
				("clkin", self.clkin),
				("trigger_reset", self.trigger_reset)
			],
			parameters=[
				("in_period", in_period),
				("f_mult", ratio.numerator),
				("f_div", ratio.denominator)
			]
		)

	def get_fragment(self):
		return Fragment(instances=[self._inst])
