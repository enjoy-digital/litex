from migen.fhdl.std import *

from misoclib import gpio, spiflash
from misoclib.gensoc import GenSoC, IntegratedBIOS

class SimpleSoC(GenSoC, IntegratedBIOS):
	def __init__(self, platform):
		GenSoC.__init__(self, platform,
			clk_freq=32*1000000,
			cpu_reset_address=0)
		IntegratedBIOS.__init__(self)

		# We can't use reset_less as LM32 does require a reset signal
		self.clock_domains.cd_sys = ClockDomain()
		self.comb += self.cd_sys.clk.eq(platform.request("clk32"))
		self.specials += Instance("FD", p_INIT=1, i_D=0, o_Q=self.cd_sys.rst, i_C=ClockSignal())

		self.submodules.leds = gpio.GPIOOut(platform.request("user_led"))

		# Map the SPI flash at 0xb0000000 for demo purposes. Later, we'll want to store the BIOS there.
		self.submodules.spiflash = spiflash.SpiFlash(platform.request("spiflash2x"),
			cmd=0xefef, cmd_width=16, addr_width=24, dummy=4)
		self.add_wb_slave(lambda a: a[26:29] == 3, self.spiflash.bus)

def get_default_subtarget(platform):
	return SimpleSoC
