from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.fhdl.specials import Instance
from migen.genlib.cdc import MultiReg
from migen.bank.description import *

class Clocking(Module, AutoReg):
	def __init__(self):
		self.clkin = Signal()

		self._r_pll_reset = RegisterField(reset=1)
		self._r_locked = RegisterField(1, READ_ONLY, WRITE_ONLY)

		self.locked = Signal()
		self.serdesstrobe = Signal()
		self._cd_pix = ClockDomain()
		self._cd_pix5x = ClockDomain()
		self._cd_pix20x = ClockDomain()

		###

		clkfbout = Signal()
		pll_locked = Signal()
		pll_clk0 = Signal()
		pll_clk1 = Signal()
		pll_clk2 = Signal()
		self.specials += Instance("PLL_BASE",
			Instance.Parameter("CLKIN_PERIOD", 22.0),
			Instance.Parameter("CLKFBOUT_MULT", 20),
			Instance.Parameter("CLKOUT0_DIVIDE", 20), # pix
			Instance.Parameter("CLKOUT1_DIVIDE", 4),  # pix5x
			Instance.Parameter("CLKOUT2_DIVIDE", 1),  # pix20x
			Instance.Parameter("COMPENSATION", "INTERNAL"),

			Instance.Output("CLKFBOUT", clkfbout),
			Instance.Output("CLKOUT0", pll_clk0),
			Instance.Output("CLKOUT1", pll_clk1),
			Instance.Output("CLKOUT2", pll_clk2),
			Instance.Output("LOCKED", pll_locked),
			Instance.Input("CLKFBIN", clkfbout),
			Instance.Input("CLKIN", self.clkin),
			Instance.Input("RST", self._r_pll_reset.field.r)
		)

		self.specials += Instance("BUFG",
			Instance.Input("I", pll_clk0), Instance.Output("O", self._cd_pix.clk))
		self.specials += Instance("BUFG",
			Instance.Input("I", pll_clk1), Instance.Output("O", self._cd_pix5x.clk))
		locked_async = Signal()
		self.specials += Instance("BUFPLL",
			Instance.Parameter("DIVIDE", 4),
			Instance.Input("PLLIN", pll_clk2),
			Instance.ClockPort("GCLK", "pix5x"),
			Instance.Input("LOCKED", pll_locked),
			Instance.Output("IOCLK", self._cd_pix20x.clk),
			Instance.Output("LOCK", locked_async),
			Instance.Output("SERDESSTROBE", self.serdesstrobe)
		)
		self.specials += MultiReg(locked_async, self.locked, "sys")
		self.comb += self._r_locked.field.w.eq(self.locked)
