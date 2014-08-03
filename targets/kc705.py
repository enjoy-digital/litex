from migen.fhdl.std import *
from migen.bus import wishbone

from misoclib.gensoc import GenSoC, IntegratedBIOS

class BaseSoC(GenSoC, IntegratedBIOS):
	default_platform = "kc705"

	def __init__(self, platform, **kwargs):
		GenSoC.__init__(self, platform,
			clk_freq=156*1000000, cpu_reset_address=0,
			**kwargs)
		IntegratedBIOS.__init__(self)

		clk200 = platform.request("clk156")
		self.specials += Instance("IBUFGDS",
				i_I=clk200.p,
				i_IB=clk200.n,
				o_O=ClockSignal()
		)
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_pwr_on = ClockDomain(reset_less=True)
		self.comb += self.cd_pwr_on.clk.eq(self.cd_sys.clk)
		self.cd_sys.rst.reset = 1
		self.sync.pwr_on += self.cd_sys.rst.eq(0)

		self.submodules.usermem = wishbone.SRAM(64*1024)
		self.add_wb_slave(lambda a: a[27:29] == 2, self.usermem.bus)
		self.add_cpu_memory_region("sdram", 0x40000000, 64*1024)

default_subtarget = BaseSoC
