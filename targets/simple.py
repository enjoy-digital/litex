from migen.fhdl.std import *
from migen.bus import wishbone

from misoclib import spiflash
from misoclib.gensoc import GenSoC

class PowerOnRst(Module):
	def __init__(self, cd, overwrite_cd_rst=True):
		self.clock_domains.cd_pwr_on = ClockDomain(reset_less=True)
		self.cd_pwr_on.clk = cd.clk
		self.pwr_on_rst = Signal()

		rst_n = Signal()
		self.sync.pwr_on += rst_n.eq(1)
		self.comb += self.pwr_on_rst.eq(~rst_n)

		if overwrite_cd_rst:
			self.comb += cd.rst.eq(self.pwr_on_rst)

class SimpleSoC(GenSoC):
	default_platform = "papilio_pro"

	def __init__(self, platform, **kwargs):
		GenSoC.__init__(self, platform,
			clk_freq=32*1000000,
			cpu_reset_address=0x60000,
			**kwargs)

		# We can't use reset_less as CPU does require a reset signal
		self.clock_domains.cd_sys = ClockDomain()
		self.submodules += PowerOnRst(self.cd_sys)
		self.comb += self.cd_sys.clk.eq(platform.request("clk32"))

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
