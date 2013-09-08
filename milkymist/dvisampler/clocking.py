from migen.fhdl.std import *
from migen.genlib.cdc import MultiReg
from migen.bank.description import *

class Clocking(Module, AutoCSR):
	def __init__(self, pads):
		self._r_pll_reset = CSRStorage(reset=1)
		self._r_locked = CSRStatus()

		self.locked = Signal()
		self.serdesstrobe = Signal()
		self.clock_domains._cd_pix = ClockDomain()
		self.clock_domains._cd_pix5x = ClockDomain()
		self.clock_domains._cd_pix10x = ClockDomain(reset_less=True)
		self.clock_domains._cd_pix20x = ClockDomain(reset_less=True)

		###

		if hasattr(pads, "clk_p"):
			clkin = Signal()
			self.specials += Instance("IBUFDS",
				Instance.Input("I", pads.clk_p),
				Instance.Input("IB", pads.clk_n),
				Instance.Output("O", clkin)		
			)
		else:
			clkin = pads.clk

		clkfbout = Signal()
		pll_locked = Signal()
		pll_clk0 = Signal()
		pll_clk1 = Signal()
		pll_clk2 = Signal()
		pll_clk3 = Signal()
		self.specials += Instance("PLL_BASE",
			Instance.Parameter("CLKIN_PERIOD", 26.7),
			Instance.Parameter("CLKFBOUT_MULT", 20),
			Instance.Parameter("CLKOUT0_DIVIDE", 1),  # pix20x
			Instance.Parameter("CLKOUT1_DIVIDE", 4),  # pix5x
			Instance.Parameter("CLKOUT2_DIVIDE", 20), # pix
			Instance.Parameter("CLKOUT3_DIVIDE", 2),  # pix10x
			Instance.Parameter("COMPENSATION", "INTERNAL"),

			Instance.Output("CLKFBOUT", clkfbout),
			# WARNING: Do not touch the order of those clocks, or PAR fails.
			Instance.Output("CLKOUT0", pll_clk0),
			Instance.Output("CLKOUT1", pll_clk1),
			Instance.Output("CLKOUT2", pll_clk2),
			Instance.Output("CLKOUT3", pll_clk3),
			Instance.Output("LOCKED", pll_locked),
			Instance.Input("CLKFBIN", clkfbout),
			Instance.Input("CLKIN", clkin),
			Instance.Input("RST", self._r_pll_reset.storage)
		)

		locked_async = Signal()
		self.specials += Instance("BUFPLL",
			Instance.Parameter("DIVIDE", 4),
			Instance.Input("PLLIN", pll_clk0),
			Instance.Input("GCLK", ClockSignal("pix5x")),
			Instance.Input("LOCKED", pll_locked),
			Instance.Output("IOCLK", self._cd_pix20x.clk),
			Instance.Output("LOCK", locked_async),
			Instance.Output("SERDESSTROBE", self.serdesstrobe)
		)
		self.specials += Instance("BUFG",
			Instance.Input("I", pll_clk1), Instance.Output("O", self._cd_pix5x.clk))
		self.specials += Instance("BUFG",
			Instance.Input("I", pll_clk2), Instance.Output("O", self._cd_pix.clk))
		self.specials += Instance("BUFG",
			Instance.Input("I", pll_clk3), Instance.Output("O", self._cd_pix10x.clk))
		self.specials += MultiReg(locked_async, self.locked, "sys")
		self.comb += self._r_locked.status.eq(self.locked)

		# sychronize pix+pix5x reset
		pix_rst_n = 1
		for i in range(2):
			new_pix_rst_n = Signal()
			self.specials += Instance("FDCE",
				Instance.Input("D", pix_rst_n),
				Instance.Input("CE", 1),
				Instance.Input("C", ClockSignal("pix")),
				Instance.Input("CLR", ~locked_async),
				Instance.Output("Q", new_pix_rst_n)
			)
			pix_rst_n = new_pix_rst_n
		self.comb += self._cd_pix.rst.eq(~pix_rst_n)
		self.comb += self._cd_pix5x.rst.eq(~pix_rst_n)
