from migen.fhdl.std import *

from misoclib import gpio
from misoclib.gensoc import GenSoC, IntegratedBIOS

class SimpleSoC(GenSoC, IntegratedBIOS):
	def __init__(self, platform):
		GenSoC.__init__(self, platform,
			clk_freq=32*1000000,
			cpu_reset_address=0,
			sram_size=4096)
		IntegratedBIOS.__init__(self)

		# We can't use reset_less as LM32 does require a reset signal
		self.clock_domains.cd_sys = ClockDomain()
		self.comb += self.cd_sys.clk.eq(platform.request("clk32"))
		self.specials += Instance("FD", p_INIT=1, i_D=0, o_Q=self.cd_sys.rst, i_C=ClockSignal())

		self.submodules.leds = gpio.GPIOOut(platform.request("user_led"))

def get_default_subtarget(platform):
	return SimpleSoC
