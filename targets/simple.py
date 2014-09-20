from migen.fhdl.std import *
from migen.bus import wishbone

from misoclib.gensoc import GenSoC, IntegratedBIOS

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

class SimpleSoC(GenSoC, IntegratedBIOS):
	default_platform = "de0nano"	# /!\ Adapt this!
	clk_name = "clk50"				# /!\ Adapt this!
	clk_freq = 50*1000000			# /!\ Adapt this!

	def __init__(self, platform):
		GenSoC.__init__(self, platform,
			clk_freq=self.clk_freq,
			cpu_reset_address=0)
		IntegratedBIOS.__init__(self)

		self.submodules.crg = _CRG(platform.request(self.clk_name))

		# use on-board SRAM as SDRAM
		sys_ram_size = 16*1024
		self.submodules.sys_ram = wishbone.SRAM(sys_ram_size)
		self.add_wb_slave(lambda a: a[27:29] == 2, self.sys_ram.bus)
		self.add_cpu_memory_region("sdram", 0x40000000, sys_ram_size)

default_subtarget = SimpleSoC
