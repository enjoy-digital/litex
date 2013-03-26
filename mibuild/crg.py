from migen.fhdl.structure import *
from migen.fhdl.module import Module

class SimpleCRG(Module):
	def __init__(self, platform, clk_name, rst_name, rst_invert=False):
			self.clock_domains.cd_sys = ClockDomain()
			self.comb += self.cd_sys.clk.eq(platform.request(clk_name))
			if rst_invert:
				self.comb += self.cd_sys.rst.eq(~platform.request(rst_name))
			else:
				self.comb += self.cd_sys.rst.eq(platform.request(rst_name))
