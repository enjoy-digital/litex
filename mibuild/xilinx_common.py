from migen.fhdl.std import *

class CRG_DS(Module):
	def __init__(self, platform, clk_name, rst_name, rst_invert=False):
		reset_less = rst_name is None
		self.clock_domains.cd_sys = ClockDomain(reset_less=reset_less)
		self._clk = platform.request(clk_name)
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

