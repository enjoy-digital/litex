from migen.fhdl.structure import *
from migen.fhdl.module import Module

class SimpleCRG(Module):
	def __init__(self, platform, clk_name, rst_name, rst_invert=False):
			self.clock_domains.cd_sys = ClockDomain()
			platform.request(clk_name, None, self.cd_sys.clk)
			if rst_invert:
				rst_n = platform.request(rst_name)
				self.comb += self.cd_sys.rst.eq(~rst_n)
			else:
				platform.request(rst_name, None, self.cd_sys.rst)
