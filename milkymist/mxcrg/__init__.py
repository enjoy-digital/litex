from fractions import Fraction

from migen.fhdl.std import *
from migen.bank.description import *

class MXCRG(Module, AutoCSR):
	def __init__(self, pads, outfreq1x):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_sdram_half = ClockDomain()
		self.clock_domains.cd_sdram_full_wr = ClockDomain()
		self.clock_domains.cd_sdram_full_rd = ClockDomain()
		self.clock_domains.cd_eth_rx = ClockDomain()
		self.clock_domains.cd_eth_tx = ClockDomain()
		self.clock_domains.cd_vga = ClockDomain(reset_less=True)

		self.clk4x_wr_strb = Signal()
		self.clk4x_rd_strb = Signal()

		self._r_cmd_data = CSRStorage(10)
		self._r_send_cmd_data = CSR()
		self._r_send_go = CSR()
		self._r_status = CSRStatus(3)

		###
		
		infreq = 50*1000000
		ratio = Fraction(outfreq1x)/Fraction(infreq)
		in_period = float(Fraction(1000000000)/Fraction(infreq))

		vga_progdata = Signal()
		vga_progen = Signal()
		vga_progdone = Signal()
		vga_locked = Signal()

		self.specials += Instance("mxcrg",
			Instance.Parameter("in_period", in_period),
			Instance.Parameter("f_mult", ratio.numerator),
			Instance.Parameter("f_div", ratio.denominator),
			Instance.Input("clk50_pad", pads.clk50),
			Instance.Input("trigger_reset", pads.trigger_reset),
			
			Instance.Input("eth_rx_clk_pad", pads.eth_rx_clk),
			Instance.Input("eth_tx_clk_pad", pads.eth_tx_clk),
			
			Instance.Output("sys_clk", self.cd_sys.clk),
			Instance.Output("sys_rst", self.cd_sys.rst),
			Instance.Output("clk2x_270", self.cd_sdram_half.clk),
			Instance.Output("clk4x_wr", self.cd_sdram_full_wr.clk),
			Instance.Output("clk4x_rd", self.cd_sdram_full_rd.clk),
			Instance.Output("eth_rx_clk", self.cd_eth_rx.clk),
			Instance.Output("eth_tx_clk", self.cd_eth_tx.clk),
			Instance.Output("vga_clk", self.cd_vga.clk),

			Instance.Output("clk4x_wr_strb", self.clk4x_wr_strb),
			Instance.Output("clk4x_rd_strb", self.clk4x_rd_strb),
			Instance.Output("norflash_rst_n", pads.norflash_rst_n),
			Instance.Output("ddr_clk_pad_p", pads.ddr_clk_p),
			Instance.Output("ddr_clk_pad_n", pads.ddr_clk_n),
			Instance.Output("eth_phy_clk_pad", pads.eth_phy_clk),
			Instance.Output("vga_clk_pad", pads.vga_clk),

			Instance.Input("vga_progclk", ClockSignal()),
			Instance.Input("vga_progdata", vga_progdata),
			Instance.Input("vga_progen", vga_progen),
			Instance.Output("vga_progdone", vga_progdone),
			Instance.Output("vga_locked", vga_locked))

		remaining_bits = Signal(max=11)
		transmitting = Signal()
		self.comb += transmitting.eq(remaining_bits != 0)
		sr = Signal(10)
		self.sync += [
			If(self._r_send_cmd_data.re,
				remaining_bits.eq(10),
				sr.eq(self._r_cmd_data.storage)
			).Elif(transmitting,
				remaining_bits.eq(remaining_bits - 1),
				sr.eq(sr[1:])
			)
		]
		self.comb += [
			vga_progdata.eq(transmitting & sr[0]),
			vga_progen.eq(transmitting | self._r_send_go.re)
		]

		# enforce gap between commands
		busy_counter = Signal(max=14)
		busy = Signal()
		self.comb += busy.eq(busy_counter != 0)
		self.sync += If(self._r_send_cmd_data.re,
				busy_counter.eq(13)
			).Elif(busy,
				busy_counter.eq(busy_counter - 1)
			)

		self.comb += self._r_status.status.eq(Cat(busy, vga_progdone, vga_locked))
