from migen.fhdl.std import *
from mibuild.crg import SimpleCRG

class CRG_SE(SimpleCRG):
	def __init__(self, platform, clk_name, rst_name, period=None, rst_invert=False):
		SimpleCRG.__init__(self, platform, clk_name, rst_name, rst_invert)
		platform.add_period_constraint(platform, self._clk, period)

class CRG_DS(Module):
	def __init__(self, platform, clk_name, rst_name, period=None, rst_invert=False):
		reset_less = rst_name is None
		self.clock_domains.cd_sys = ClockDomain(reset_less=reset_less)
		self._clk = platform.request(clk_name)
		platform.add_period_constraint(platform, self._clk.p, period)
		self.specials += Instance("IBUFGDS",
			Instance.Input("I", self._clk.p),
			Instance.Input("IB", self._clk.n),
			Instance.Output("O", self.cd_sys.clk)
		)
		if not reset_less:
			if rst_invert:
				self.comb += self.cd_sys.rst.eq(~platform.request(rst_name))
			else:
				self.comb += self.cd_sys.rst.eq(platform.request(rst_name))

