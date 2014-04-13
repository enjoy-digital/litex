from migen.fhdl.std import *
from migen.bus import wishbone

from misoclib import spiflash
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
		self.flash_boot_address = 0x70000
		self.register_rom(self.spiflash.bus)

		# TODO: use on-board SDRAM instead of block RAM
		sys_ram_size = 32*1024
		self.submodules.sys_ram = wishbone.SRAM(sys_ram_size)
		self.add_wb_slave(lambda a: a[27:29] == 2, self.sys_ram.bus)
		self.add_cpu_memory_region("sdram", 0x40000000, sys_ram_size)

default_subtarget = SimpleSoC
