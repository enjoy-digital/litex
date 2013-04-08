from migen.fhdl.structure import *
from migen.fhdl.module import Module

class SimpleCRG(Module):
	def __init__(self, platform, clk_name, rst_name, rst_invert=False):
			self._clk = platform.request(clk_name)
			self._rst = platform.request(rst_name)
			self.clock_domains.cd_sys = ClockDomain()
			self.comb += self.cd_sys.clk.eq(self._clk)
			if rst_invert:
				self.comb += self.cd_sys.rst.eq(~self._rst)
			else:
				self.comb += self.cd_sys.rst.eq(self._rst)
