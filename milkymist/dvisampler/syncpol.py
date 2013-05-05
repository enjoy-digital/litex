from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.genlib.record import Record

from milkymist.dvisampler.common import channel_layout

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
