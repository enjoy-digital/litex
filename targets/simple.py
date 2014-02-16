from migen.fhdl.std import *

from misoclib import gpio, spiflash
from misoclib.gensoc import GenSoC

class SimpleSoC(GenSoC):
	default_platform = "papilio_pro"

	def __init__(self, platform):
		GenSoC.__init__(self, platform,
			clk_freq=32*1000000,
			cpu_reset_address=0x60000)

		# We can't use reset_less as LM32 does require a reset signal
		self.clock_domains.cd_sys = ClockDomain()
		self.comb += self.cd_sys.clk.eq(platform.request("clk32"))
		self.specials += Instance("FD", p_INIT=1, i_D=0, o_Q=self.cd_sys.rst, i_C=ClockSignal())

		# BIOS is in SPI flash
		self.submodules.spiflash = spiflash.SpiFlash(platform.request("spiflash2x"),
			cmd=0xefef, cmd_width=16, addr_width=24, dummy=4)
		self.register_rom(self.spiflash.bus)

		self.submodules.leds = gpio.GPIOOut(platform.request("user_led"))

default_subtarget = SimpleSoC
