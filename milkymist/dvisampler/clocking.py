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

		###

		clk_se = Signal()
		self.specials += Instance("IBUFDS", i_I=pads.clk_p, i_IB=pads.clk_n, o_O=clk_se)

		clkfbout = Signal()
		pll_locked = Signal()
		pll_clk0 = Signal()
		pll_clk1 = Signal()
		pll_clk2 = Signal()
		self.specials += Instance("PLL_BASE",
			p_CLKIN_PERIOD=26.7,
			p_CLKFBOUT_MULT=20,
			p_CLKOUT0_DIVIDE=2,  # pix10x
			p_CLKOUT1_DIVIDE=4,  # pix5x
			p_CLKOUT2_DIVIDE=20, # pix
			p_COMPENSATION="INTERNAL",
			
			i_CLKIN=clk_se,
			o_CLKOUT0=pll_clk0, o_CLKOUT1=pll_clk1, o_CLKOUT2=pll_clk2,
			o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbout,
			o_LOCKED=pll_locked, i_RST=self._r_pll_reset.storage)

		locked_async = Signal()
		self.specials += [
			Instance("BUFPLL", p_DIVIDE=2,
				i_PLLIN=pll_clk0, i_GCLK=ClockSignal("pix5x"), i_LOCKED=pll_locked,
				o_IOCLK=self._cd_pix10x.clk, o_LOCK=locked_async, o_SERDESSTROBE=self.serdesstrobe),
			Instance("BUFG", i_I=pll_clk1, o_O=self._cd_pix5x.clk),
			Instance("BUFG", i_I=pll_clk2, o_O=self._cd_pix.clk),
			MultiReg(locked_async, self.locked, "sys")
		]
		self.comb += self._r_locked.status.eq(self.locked)

		# sychronize pix+pix5x reset
		pix_rst_n = 1
		for i in range(2):
			new_pix_rst_n = Signal()
			self.specials += Instance("FDCE", i_D=pix_rst_n, i_CE=1, i_C=ClockSignal("pix"),
				i_CLR=~locked_async, o_Q=new_pix_rst_n)
			pix_rst_n = new_pix_rst_n
		self.comb += self._cd_pix.rst.eq(~pix_rst_n), self._cd_pix5x.rst.eq(~pix_rst_n)
