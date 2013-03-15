from migen.fhdl.structure import *
from migen.fhdl.module import Module

class CRG(Module):
	def get_clock_domains(self):
		r = dict()
		for k, v in self.__dict__.items():
			if isinstance(v, ClockDomain):
				r[v.name] = v
		return r

class SimpleCRG(CRG):
	def __init__(self, platform, clk_name, rst_name, rst_invert=False):
			self.cd = ClockDomain("sys")
			platform.request(clk_name, None, self.cd.clk)
			if rst_invert:
				rst_n = platform.request(rst_name)
				self.comb += self.cd.rst.eq(~rst_n)
			else:
				platform.request(rst_name, None, self.cd.rst)
