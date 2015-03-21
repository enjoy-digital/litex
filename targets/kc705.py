from migen.fhdl.std import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from misoclib.mem import sdram
from misoclib.mem.sdram.module import MT8JTF12864
from misoclib.mem.sdram.phy import k7ddrphy
from misoclib.mem.sdram.core.lasmicon import LASMIconSettings
from misoclib.mem.flash import spiflash
from misoclib.soc import mem_decoder
from misoclib.soc.sdram import SDRAMSoC

from misoclib.com.liteeth.phy import LiteEthPHY
from misoclib.com.liteeth.mac import LiteEthMAC

class _CRG(Module):
	def __init__(self, platform):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
		self.clock_domains.cd_clk200 = ClockDomain()

		clk200 = platform.request("clk200")
		clk200_se = Signal()
		self.specials += Instance("IBUFDS", i_I=clk200.p, i_IB=clk200.n, o_O=clk200_se)

		rst = platform.request("cpu_reset")

		pll_locked = Signal()
		pll_fb = Signal()
		self.pll_sys = Signal()
		pll_sys4x = Signal()
		pll_clk200 = Signal()
		self.specials += [
			Instance("PLLE2_BASE",
				p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

				# VCO @ 1GHz
				p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=5.0,
				p_CLKFBOUT_MULT=5, p_DIVCLK_DIVIDE=1,
				i_CLKIN1=clk200_se, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

				# 125MHz
				p_CLKOUT0_DIVIDE=8, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=self.pll_sys,

				# 500MHz
				p_CLKOUT1_DIVIDE=2, p_CLKOUT1_PHASE=0.0, o_CLKOUT1=pll_sys4x,

				# 200MHz
				p_CLKOUT2_DIVIDE=5, p_CLKOUT2_PHASE=0.0, o_CLKOUT2=pll_clk200,

				p_CLKOUT3_DIVIDE=2, p_CLKOUT3_PHASE=0.0, #o_CLKOUT3=,

				p_CLKOUT4_DIVIDE=4, p_CLKOUT4_PHASE=0.0, #o_CLKOUT4=
			),
			Instance("BUFG", i_I=self.pll_sys, o_O=self.cd_sys.clk),
			Instance("BUFG", i_I=pll_sys4x, o_O=self.cd_sys4x.clk),
			Instance("BUFG", i_I=pll_clk200, o_O=self.cd_clk200.clk),
			AsyncResetSynchronizer(self.cd_sys, ~pll_locked | rst),
			AsyncResetSynchronizer(self.cd_clk200, ~pll_locked | rst),
		]

		reset_counter = Signal(4, reset=15)
		ic_reset = Signal(reset=1)
		self.sync.clk200 += \
			If(reset_counter != 0,
				reset_counter.eq(reset_counter - 1)
			).Else(
				ic_reset.eq(0)
			)
		self.specials += Instance("IDELAYCTRL", i_REFCLK=ClockSignal("clk200"), i_RST=ic_reset)

class BaseSoC(SDRAMSoC):
	default_platform = "kc705"

	csr_map = {
		"spiflash":	16,
		"ddrphy":	17,
	}
	csr_map.update(SDRAMSoC.csr_map)

	def __init__(self, platform, sdram_controller_settings=LASMIconSettings(), **kwargs):
		SDRAMSoC.__init__(self, platform,
			clk_freq=125*1000000, cpu_reset_address=0xaf0000,
			sdram_controller_settings=sdram_controller_settings,
			**kwargs)

		self.submodules.crg = _CRG(platform)

		if not self.with_integrated_main_ram:
			sdram_modules = MT8JTF12864(self.clk_freq)
			self.submodules.ddrphy = k7ddrphy.K7DDRPHY(platform.request("ddram"), memtype="DDR3")
			self.register_sdram_phy(self.ddrphy, sdram_modules.geom_settings, sdram_modules.timing_settings)

		spiflash_pads = platform.request("spiflash")
		spiflash_pads.clk = Signal()
		self.specials += Instance("STARTUPE2",
			i_CLK=0, i_GSR=0, i_GTS=0, i_KEYCLEARB=0, i_PACK=0,
			i_USRCCLKO=spiflash_pads.clk, i_USRCCLKTS=0, i_USRDONEO=1, i_USRDONETS=1)
		self.submodules.spiflash = spiflash.SpiFlash(spiflash_pads, dummy=11, div=2)
		self.flash_boot_address = 0xb00000

		# If not in ROM, BIOS is in SPI flash
		if not self.with_integrated_rom:
			self.register_rom(self.spiflash.bus)

class MiniSoC(BaseSoC):
	csr_map = {
		"ethphy":		18,
		"ethmac":		19,
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
		self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32, interface="wishbone")
		self.add_wb_slave(mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus)
		self.add_memory_region("ethmac", self.mem_map["ethmac"]+0x80000000, 0x2000)

default_subtarget = BaseSoC
