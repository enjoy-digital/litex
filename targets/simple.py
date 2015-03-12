from migen.fhdl.std import *
from migen.bus import wishbone

from misoclib.soc import SoC, mem_decoder
from misoclib.com.liteeth.phy import LiteEthPHY
from misoclib.com.liteeth.mac import LiteEthMAC

class _CRG(Module):
	def __init__(self, clk_crg):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_por = ClockDomain(reset_less=True)

		# Power on Reset (vendor agnostic)
		rst_n = Signal()
		self.sync.por += rst_n.eq(1)
		self.comb += [
			self.cd_sys.clk.eq(clk_crg),
			self.cd_por.clk.eq(clk_crg),
			self.cd_sys.rst.eq(~rst_n)
		]

class BaseSoC(SoC):
	def __init__(self, platform, **kwargs):
		SoC.__init__(self, platform,
			clk_freq=int((1/(platform.default_clk_period))*1000000000),
			with_rom=True,
			with_sdram=True, sdram_size=16*1024,
			**kwargs)
		clk_in = platform.request(platform.default_clk_name)
		clk_crg = Signal()
		if hasattr(clk_in, "p"):
			from mibuild.xilinx.vivado import XilinxVivadoPlatform
			from mibuild.xilinx.ise import XilinxISEPlatform
			if isinstance(platform, (XilinxISEPlatform, XilinxVivadoPlatform)):
				self.specials += Instance("IBUFDS", i_I=clk_in.p, i_IB=clk_in.n, o_O=clk_crg)
			else:
				raise NotImplementedError
		else:
			self.comb += clk_crg.eq(clk_in)
		self.submodules.crg = _CRG(clk_crg)

class MiniSoC(BaseSoC):
	csr_map = {
		"ethphy":		20,
		"ethmac":		21
	}
	csr_map.update(BaseSoC.csr_map)

	interrupt_map = {
		"ethmac":		2,
	}
	interrupt_map.update(BaseSoC.interrupt_map)

	mem_map = {
		"ethmac":	0x30000000, # (shadow @0xb0000000)
	}
	mem_map.update(BaseSoC.mem_map)

	def __init__(self, platform, **kwargs):
		BaseSoC.__init__(self, platform, **kwargs)

		self.submodules.ethphy = LiteEthPHY(platform.request("eth_clocks"), platform.request("eth"))
		self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32, interface="wishbone", with_hw_preamble_crc=False)
		self.add_wb_slave(mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus)
		self.add_memory_region("ethmac", self.mem_map["ethmac"]+0x80000000, 0x2000)

default_subtarget = BaseSoC
