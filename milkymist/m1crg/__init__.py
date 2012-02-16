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
			"clk2x_90",
			"clk4x_wr_left",
			"clk4x_wr_strb_left",
			"clk4x_wr_right",
			"clk4x_wr_strb_right",
			"clk4x_rd_left",
			"clk4x_rd_strb_left",
			"clk4x_rd_right",
			"clk4x_rd_strb_right"
		  ]:
			s = Signal(name=name)
			setattr(self, name, s)
			generated.append((name, s))  
		
		self.rd_clk_lb = Signal()
		
		ratio = Fraction(outfreq1x)/Fraction(infreq)
		in_period = float(Fraction(1000000000)/Fraction(infreq))
		
		self._inst = Instance("m1crg",
			generated,
			[
				("clkin", self.clkin),
				("trigger_reset", self.trigger_reset),
				("rd_clk_lb", self.rd_clk_lb) # TODO: inout
			], [
				("in_period", in_period),
				("f_mult", ratio.numerator),
				("f_div", ratio.denominator)
			]
		)

	def get_fragment(self):
		return Fragment(instances=[self._inst],
			pads={self.clkin, self.ac97_rst_n, self.videoin_rst_n, self.flash_rst_n, self.rd_clk_lb})
