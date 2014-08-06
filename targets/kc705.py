from migen.fhdl.std import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.bus import wishbone

from misoclib.gensoc import GenSoC, IntegratedBIOS

class _CRG(Module):
	def __init__(self, platform):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
		self.clock_domains.cd_clk200 = ClockDomain()

		clk200 = platform.request("clk200")
		clk200_se = Signal()
		self.specials += Instance("IBUFDS", i_I=clk200.p, i_IB=clk200.n, o_O=clk200_se)

		pll_locked = Signal()
		pll_fb = Signal()
		pll_sys = Signal()
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
				p_CLKOUT0_DIVIDE=8, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=pll_sys,

				# 500MHz
				p_CLKOUT1_DIVIDE=2, p_CLKOUT1_PHASE=0.0, o_CLKOUT1=pll_sys4x,

				# 200MHz
				p_CLKOUT2_DIVIDE=5, p_CLKOUT2_PHASE=0.0, o_CLKOUT2=pll_clk200,

				p_CLKOUT3_DIVIDE=2, p_CLKOUT3_PHASE=0.0, #o_CLKOUT3=,

				p_CLKOUT4_DIVIDE=4, p_CLKOUT4_PHASE=0.0, #o_CLKOUT4=
			),
			Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
			Instance("BUFG", i_I=pll_sys4x, o_O=self.cd_sys4x.clk),
			Instance("BUFG", i_I=pll_clk200, o_O=self.cd_clk200.clk),
			AsyncResetSynchronizer(self.cd_sys, ~pll_locked),
			AsyncResetSynchronizer(self.cd_clk200, ~pll_locked),
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

class BaseSoC(GenSoC, IntegratedBIOS):
	default_platform = "kc705"

	def __init__(self, platform, **kwargs):
		GenSoC.__init__(self, platform,
			clk_freq=125*1000000, cpu_reset_address=0,
			**kwargs)
		IntegratedBIOS.__init__(self)

		self.submodules.crg = _CRG(platform)

		self.submodules.usermem = wishbone.SRAM(64*1024)
		self.add_wb_slave(lambda a: a[27:29] == 2, self.usermem.bus)
		self.add_cpu_memory_region("sdram", 0x40000000, 64*1024)

default_subtarget = BaseSoC
