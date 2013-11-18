from migen.fhdl.std import *
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.cdc import MultiReg
from migen.bank.description import *
from migen.flow.actor import *

from misoclib.framebuffer.format import bpc_phy, phy_layout
from misoclib.framebuffer import dvi

class _FIFO(Module):
	def __init__(self, pack_factor):
		self.phy = Sink(phy_layout(pack_factor))
		self.busy = Signal()
		
		self.pix_hsync = Signal()
		self.pix_vsync = Signal()
		self.pix_de = Signal()
		self.pix_r = Signal(bpc_phy)
		self.pix_g = Signal(bpc_phy)
		self.pix_b = Signal(bpc_phy)
	
		###

		fifo = RenameClockDomains(AsyncFIFO(phy_layout(pack_factor), 512),
			{"write": "sys", "read": "pix"})
		self.submodules += fifo
		self.comb += [
			self.phy.ack.eq(fifo.writable),
			fifo.we.eq(self.phy.stb),
			fifo.din.eq(self.phy.payload),
			self.busy.eq(0)
		]

		unpack_counter = Signal(max=pack_factor)
		assert(pack_factor & (pack_factor - 1) == 0) # only support powers of 2
		self.sync.pix += [
			unpack_counter.eq(unpack_counter + 1),
			self.pix_hsync.eq(fifo.dout.hsync),
			self.pix_vsync.eq(fifo.dout.vsync),
			self.pix_de.eq(fifo.dout.de)
		]
		for i in range(pack_factor):
			pixel = getattr(fifo.dout, "p"+str(i))
			self.sync.pix += If(unpack_counter == i,
				self.pix_r.eq(pixel.r),
				self.pix_g.eq(pixel.g),
				self.pix_b.eq(pixel.b)
			)
		self.comb += fifo.re.eq(unpack_counter == (pack_factor - 1))

# This assumes a 50MHz base clock
class _Clocking(Module, AutoCSR):
	def __init__(self, pads_vga, pads_dvi):
		self._r_cmd_data = CSRStorage(10)
		self._r_send_cmd_data = CSR()
		self._r_send_go = CSR()
		self._r_status = CSRStatus(4)

		self.clock_domains.cd_pix = ClockDomain(reset_less=True)
		if pads_dvi is not None:
			self._r_pll_reset = CSRStorage()
			self._r_pll_adr = CSRStorage(5)
			self._r_pll_dat_r = CSRStatus(16)
			self._r_pll_dat_w = CSRStorage(16)
			self._r_pll_read = CSR()
			self._r_pll_write = CSR()
			self._r_pll_drdy = CSRStatus()

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
			pll_drdy = Signal()
			self.sync += If(self._r_pll_read.re | self._r_pll_write.re,
				self._r_pll_drdy.status.eq(0)
			).Elif(pll_drdy,
				self._r_pll_drdy.status.eq(1)
			)
			self.specials += [
				Instance("PLL_ADV",
					p_CLKFBOUT_MULT=10,
					p_CLKOUT0_DIVIDE=1,  # pix10x
					p_CLKOUT1_DIVIDE=5,  # pix2x
					p_CLKOUT2_DIVIDE=10, # pix
					p_COMPENSATION="INTERNAL",
					
					i_CLKINSEL=1,
					i_CLKIN1=clk_pix_unbuffered,
					o_CLKOUT0=pll_clk0, o_CLKOUT1=pll_clk1, o_CLKOUT2=pll_clk2,
					o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbout,
					o_LOCKED=pll_locked, 
					i_RST=~pix_locked | self._r_pll_reset.storage,

					i_DADDR=self._r_pll_adr.storage,
					o_DO=self._r_pll_dat_r.status,
					i_DI=self._r_pll_dat_w.storage,
					i_DEN=self._r_pll_read.re | self._r_pll_write.re,
					i_DWE=self._r_pll_write.re,
					o_DRDY=pll_drdy,
					i_DCLK=ClockSignal()),
				Instance("BUFPLL", p_DIVIDE=5,
					i_PLLIN=pll_clk0, i_GCLK=ClockSignal("pix2x"), i_LOCKED=pll_locked,
					o_IOCLK=self.cd_pix10x.clk, o_LOCK=locked_async, o_SERDESSTROBE=self.serdesstrobe),
				Instance("BUFG", i_I=pll_clk1, o_O=self.cd_pix2x.clk),
				Instance("BUFG", name="dviout_pix_bufg", i_I=pll_clk2, o_O=self.cd_pix.clk),
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
			self.specials += Instance("OBUFDS", i_I=dvi_clk_se,
				o_O=pads_dvi.clk_p, o_OB=pads_dvi.clk_n)

class Driver(Module, AutoCSR):
	def __init__(self, pack_factor, pads_vga, pads_dvi):
		fifo = _FIFO(pack_factor)
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
		if pads_dvi is not None:
			self.submodules.dvi_phy = dvi.PHY(self.clocking.serdesstrobe, pads_dvi)
			self.comb += [
				self.dvi_phy.hsync.eq(fifo.pix_hsync),
				self.dvi_phy.vsync.eq(fifo.pix_vsync),
				self.dvi_phy.de.eq(fifo.pix_de),
				self.dvi_phy.r.eq(fifo.pix_r),
				self.dvi_phy.g.eq(fifo.pix_g),
				self.dvi_phy.b.eq(fifo.pix_b)
			]
