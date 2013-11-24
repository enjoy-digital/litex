from migen.fhdl.std import *
from migen.bus import wishbone

from misoclib.gensoc import GenSoC

class SimpleSoC(GenSoC):
	def __init__(self, platform):
		GenSoC.__init__(self, platform,
			clk_freq=32*1000000,
			cpu_reset_address=0,
			sram_size=4096)

		# We can't use reset_less as LM32 does require a reset signal
		self.clock_domains.cd_sys = ClockDomain()
		self.comb += self.cd_sys.clk.eq(platform.request("clk32"))
		self.specials += Instance("FD", p_INIT=1, i_D=0, o_Q=self.cd_sys.rst, i_C=ClockSignal())

		self.submodules.rom = wishbone.SRAM(32768)
		self.register_rom(self.rom.bus)

	def init_bios_memory(self, data):
		self.rom.mem.init = data

def get_default_subtarget(platform):
	return SimpleSoC
