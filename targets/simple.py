from migen.fhdl.std import *
from migen.bus import wishbone

from misoclib.gensoc import GenSoC, IntegratedBIOS, mem_decoder

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
	mem_map = {
		"sdram":	0x40000000, # (shadow @0xc0000000)
	}
	mem_map.update(GenSoC.mem_map)

	def __init__(self, platform):
		GenSoC.__init__(self, platform,
			clk_freq=int((1/(platform.default_clk_period))*1000000000),
			cpu_reset_address=0)
		IntegratedBIOS.__init__(self)

		self.submodules.crg = _CRG(platform.request(platform.default_clk_name))

		# use on-board SRAM as SDRAM
		sys_ram_size = 16*1024
		self.submodules.sys_ram = wishbone.SRAM(sys_ram_size)
		self.add_wb_slave(mem_decoder(self.mem_map["sdram"]), self.sys_ram.bus)
		self.add_cpu_memory_region("sdram", self.mem_map["sdram"], sys_ram_size)

default_subtarget = SimpleSoC
