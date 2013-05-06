from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.genlib.cdc import MultiReg
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.record import Record
from migen.bank.description import *
from migen.flow.actor import *

from milkymist.dvisampler.common import channel_layout, frame_layout

class SyncPolarity(Module):
	def __init__(self):
		self.valid_i = Signal()
		self.data_in0 = Record(channel_layout)
		self.data_in1 = Record(channel_layout)
		self.data_in2 = Record(channel_layout)

		self.valid_o = Signal()
		self.de = Signal()
		self.hsync = Signal()
		self.vsync = Signal()
		self.r = Signal(8)
		self.g = Signal(8)
		self.b = Signal(8)

		###

		de = self.data_in0.de
		de_r = Signal()
		c = self.data_in0.c
		c_polarity = Signal(2)
		c_out = Signal(2)

		self.comb += [
			self.de.eq(de_r),
			self.hsync.eq(c_out[0]),
			self.vsync.eq(c_out[1])
		]

		self.sync.pix += [
			self.valid_o.eq(self.valid_i),
			self.r.eq(self.data_in2.d),
			self.g.eq(self.data_in1.d),
			self.b.eq(self.data_in0.d),

			de_r.eq(de),
			If(de_r & ~de,
				c_polarity.eq(c),
				c_out.eq(0)
			).Else(
				c_out.eq(c ^ c_polarity)
			)
		]

class ResolutionDetection(Module, AutoCSR):
	def __init__(self, nbits=11):
		self.valid_i = Signal()
		self.vsync = Signal()
		self.de = Signal()

		self._hres = CSRStatus(nbits)
		self._vres = CSRStatus(nbits)

		###

		# Detect DE transitions
		de_r = Signal()
		pn_de = Signal()
		self.sync.pix += de_r.eq(self.de)
		self.comb += pn_de.eq(~self.de & de_r)

		# HRES
		hcounter = Signal(nbits)
		self.sync.pix += If(self.valid_i & self.de,
				hcounter.eq(hcounter + 1)
			).Else(
				hcounter.eq(0)
			)

		hcounter_st = Signal(nbits)
		self.sync.pix += If(self.valid_i,
				If(pn_de, hcounter_st.eq(hcounter))
			).Else(
				hcounter_st.eq(0)
			)
		self.specials += MultiReg(hcounter_st, self._hres.status)

		# VRES
		vsync_r = Signal()
		p_vsync = Signal()
		self.sync.pix += vsync_r.eq(self.vsync),
		self.comb += p_vsync.eq(self.vsync & ~vsync_r)

		vcounter = Signal(nbits)
		self.sync.pix += If(self.valid_i & p_vsync,
				vcounter.eq(0)
			).Elif(pn_de,
				vcounter.eq(vcounter + 1)
			)

		vcounter_st = Signal(nbits)
		self.sync.pix += If(self.valid_i,
				If(p_vsync, vcounter_st.eq(vcounter))
			).Else(
				vcounter_st.eq(0)
			)
		self.specials += MultiReg(vcounter_st, self._vres.status)

class FrameExtraction(Module):
	def __init__(self):
		# in pix clock domain
		self.valid_i = Signal()
		self.vsync = Signal()
		self.de = Signal()
		self.r = Signal(8)
		self.g = Signal(8)
		self.b = Signal(8)

		# in sys clock domain
		self.frame = Source(frame_layout)
		self.busy = Signal()

		###

		fifo_stb = Signal()
		fifo_in = Record(frame_layout)
		self.comb += [
			fifo_stb.eq(self.valid_i & self.de),
			fifo_in.r.eq(self.r),
			fifo_in.g.eq(self.g),
			fifo_in.b.eq(self.b),
		]
		vsync_r = Signal()
		self.sync.pix += [
			If(self.vsync & ~vsync_r, fifo_in.parity.eq(~fifo_in.parity)),
			vsync_r.eq(self.vsync)
		]

		fifo = AsyncFIFO(layout_len(frame_layout), 256)
		self.add_submodule(fifo, {"write": "pix", "read": "sys"})
		self.comb += [
			fifo.we.eq(fifo_stb),
			fifo.din.eq(fifo_in.raw_bits()),
			self.frame.stb.eq(fifo.readable),
			self.frame.payload.raw_bits().eq(fifo.dout),
			fifo.re.eq(self.frame.ack),
			self.busy.eq(0)
		]
