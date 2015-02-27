from migen.fhdl.std import *
from migen.bus import wishbone

from misoclib.gensoc import GenSoC, mem_decoder

class _CRG(Module):
	def __init__(self, clk_in):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_por = ClockDomain(reset_less=True)

		# Power on Reset (vendor agnostic)
		rst_n = Signal()
		self.sync.por += rst_n.eq(1)
		self.comb += [
			self.cd_sys.clk.eq(clk_in),
			self.cd_por.clk.eq(clk_in),
			self.cd_sys.rst.eq(~rst_n)
		]

class SimpleSoC(GenSoC):
	def __init__(self, platform, **kwargs):
		GenSoC.__init__(self, platform,
			clk_freq=int((1/(platform.default_clk_period))*1000000000),
			with_rom=True,
			with_sdram=True, sdram_size=16*1024,
			**kwargs)
		self.submodules.crg = _CRG(platform.request(platform.default_clk_name))

default_subtarget = SimpleSoC
