from migen.fhdl.std import *
from migen.genlib.record import Record
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.cdc import MultiReg
from migen.bank.description import *
from migen.flow.actor import *

from milkymist.framebuffer.format import bpc_phy, phy_layout

class _FIFO(Module):
	def __init__(self):
		self.phy = Sink(phy_layout)
		self.busy = Signal()
		
		self.pix_hsync = Signal()
		self.pix_vsync = Signal()
		self.pix_r = Signal(bpc_phy)
		self.pix_g = Signal(bpc_phy)
		self.pix_b = Signal(bpc_phy)
	
		###

		data_width = 2+2*3*bpc_phy
		fifo = RenameClockDomains(AsyncFIFO(data_width, 512),
			{"write": "sys", "read": "pix"})
		self.submodules += fifo
		fifo_in = self.phy.payload
		fifo_out = Record(phy_layout)
		self.comb += [
			self.phy.ack.eq(fifo.writable),
			fifo.we.eq(self.phy.stb),
			fifo.din.eq(fifo_in.raw_bits()),
			fifo_out.raw_bits().eq(fifo.dout),
			self.busy.eq(0)
		]

		pix_parity = Signal()
		self.sync.pix += [
			pix_parity.eq(~pix_parity),
			self.pix_hsync.eq(fifo_out.hsync),
			self.pix_vsync.eq(fifo_out.vsync),
			If(pix_parity,
				self.pix_r.eq(fifo_out.p1.r),
				self.pix_g.eq(fifo_out.p1.g),
				self.pix_b.eq(fifo_out.p1.b)
			).Else(
				self.pix_r.eq(fifo_out.p0.r),
				self.pix_g.eq(fifo_out.p0.g),
				self.pix_b.eq(fifo_out.p0.b)
			)
		]
		self.comb += fifo.re.eq(pix_parity)

# This assumes a 50MHz base clock
class _Clocking(Module, AutoCSR):
	def __init__(self, pads_vga, pads_dvi):
		self._r_cmd_data = CSRStorage(10)
		self._r_send_cmd_data = CSR()
		self._r_send_go = CSR()
		self._r_status = CSRStatus(4)

		self.clock_domains.cd_pix = ClockDomain(reset_less=True)
		if pads_dvi is not None:
			self.clock_domains.cd_pix2x = ClockDomain(reset_less=True)
			self.clock_domains.cd_pix10x = ClockDomain(reset_less=True)
			self.serdesstrobe = Signal()

		###

		# Generate 1x pixel clock
		clk_pix_unbuffered = Signal()
		pix_progdata = Signal()
		pix_progen = Signal()
		pix_progdone = Signal()
		pix_locked = Signal()
		self.specials += Instance("DCM_CLKGEN",
			p_CLKFXDV_DIVIDE=2, p_CLKFX_DIVIDE=4, p_CLKFX_MD_MAX=1.0, p_CLKFX_MULTIPLY=2,
			p_CLKIN_PERIOD=20.0, p_SPREAD_SPECTRUM="NONE", p_STARTUP_WAIT="FALSE",
		
			i_CLKIN=ClockSignal("base50"), o_CLKFX=clk_pix_unbuffered,
			i_PROGCLK=ClockSignal(), i_PROGDATA=pix_progdata, i_PROGEN=pix_progen,
			o_PROGDONE=pix_progdone, o_LOCKED=pix_locked,
			i_FREEZEDCM=0, i_RST=ResetSignal())

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
			pix_progdata.eq(transmitting & sr[0]),
			pix_progen.eq(transmitting | self._r_send_go.re)
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

		mult_locked = Signal()
		self.comb += self._r_status.status.eq(Cat(busy, pix_progdone, pix_locked, mult_locked))

		# Clock multiplication and buffering
		if pads_dvi is None:
			# Just buffer 1x pixel clock
			self.specials += Instance("BUFG", i_I=clk_pix_unbuffered, o_O=self.cd_pix.clk)
			self.comb += mult_locked.eq(pix_locked)
		else:
			# Route unbuffered 1x pixel clock to PLL
			# Generate 1x, 2x and 10x IO pixel clocks
			clkfbout = Signal()
			pll_locked = Signal()
			pll_clk0 = Signal()
			pll_clk1 = Signal()
			pll_clk2 = Signal()
			locked_async = Signal()
			self.specials += [
				Instance("PLL_BASE",
					p_CLKIN_PERIOD=26.7,
					p_CLKFBOUT_MULT=20,
					p_CLKOUT0_DIVIDE=2,  # pix10x
					p_CLKOUT1_DIVIDE=10, # pix2x
					p_CLKOUT2_DIVIDE=20, # pix
					p_COMPENSATION="INTERNAL",
					
					i_CLKIN=clk_pix_unbuffered,
					o_CLKOUT0=pll_clk0, o_CLKOUT1=pll_clk1, o_CLKOUT2=pll_clk2,
					o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbout,
					o_LOCKED=pll_locked, i_RST=~pix_locked),
				Instance("BUFPLL", p_DIVIDE=5,
					i_PLLIN=pll_clk0, i_GCLK=ClockSignal("pix2x"), i_LOCKED=pll_locked,
					o_IOCLK=self.cd_pix10x.clk, o_LOCK=locked_async, o_SERDESSTROBE=self.serdesstrobe),
				Instance("BUFG", i_I=pll_clk1, o_O=self.cd_pix2x.clk),
				Instance("BUFG", i_I=pll_clk2, o_O=self.cd_pix.clk),
				MultiReg(locked_async, mult_locked, "sys")
			]

		# Drive VGA/DVI clock pads
		if pads_vga is not None:
			self.specials += Instance("ODDR2",
				p_DDR_ALIGNMENT="NONE", p_INIT=0, p_SRTYPE="SYNC",
				o_Q=pads_vga.clk,
				i_C0=ClockSignal("pix"),
				i_C1=~ClockSignal("pix"),
				i_CE=1, i_D0=1, i_D1=0,
				i_R=0, i_S=0)
		if pads_dvi is not None:
			dvi_clk_se = Signal()
			self.specials += Instance("ODDR2",
				p_DDR_ALIGNMENT="NONE", p_INIT=0, p_SRTYPE="SYNC",
				o_Q=dvi_clk_se,
				i_C0=ClockSignal("pix"),
				i_C1=~ClockSignal("pix"),
				i_CE=1, i_D0=1, i_D1=0,
				i_R=0, i_S=0)
			self.specials += Instance("OBUFTDS", i_I=dvi_clk_se,
				o_O=pads_dvi.clk_p, o_OB=pads_dvi.clk_n)

class Driver(Module, AutoCSR):
	def __init__(self, pads_vga, pads_dvi):
		fifo = _FIFO()
		self.submodules += fifo
		self.phy = fifo.phy
		self.busy = fifo.busy

		self.submodules.clocking = _Clocking(pads_vga, pads_dvi)

		if pads_vga is not None:
			self.comb += [
				pads_vga.hsync_n.eq(~fifo.pix_hsync),
				pads_vga.vsync_n.eq(~fifo.pix_vsync),
				pads_vga.r.eq(fifo.pix_r),
				pads_vga.g.eq(fifo.pix_g),
				pads_vga.b.eq(fifo.pix_b),
				pads_vga.psave_n.eq(1)
			]
