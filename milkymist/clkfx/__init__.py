from fractions import Fraction

from migen.fhdl.structure import *

class Inst:
	def __init__(self, infreq, outfreq):
		declare_signal(self, "clkin")
		declare_signal(self, "clkout")
		
		ratio = Fraction(outfreq)/Fraction(infreq)
		appr = ratio.limit_denominator(32)
		m = appr.numerator
		if m < 2 or m > 32:
			raise OverflowError
		d = appr.denominator
		
		in_period = float(Fraction(1000000000)/Fraction(infreq))
		
		self._inst = Instance("DCM_SP",
			[("CLKFX", self.clkout)],
			[("CLKIN", self.clkin),
			("PSEN", BV(1)),
			("RST", BV(1))],
			[("CLKDV_DIVIDE", 2.0),
			("CLKFX_DIVIDE", d),
			("CLKFX_MULTIPLY", m),
			("CLKIN_DIVIDE_BY_2", "FALSE"),
			("CLKIN_PERIOD", in_period),
			("CLKOUT_PHASE_SHIFT", "NONE"),
			("CLK_FEEDBACK", "NONE"),
			("DESKEW_ADJUST", "SYSTEM_SYNCHRONOUS"),
			("DUTY_CYCLE_CORRECTION", "TRUE"),
			("PHASE_SHIFT", 0),
			("STARTUP_WAIT", "TRUE")]
		)

	def get_fragment(self):
		return Fragment([self._inst.ins["PSEN"].eq(0), self._inst.ins["RST"].eq(0)], instances=[self._inst])
