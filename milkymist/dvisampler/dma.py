from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *
from migen.flow.actor import *
from migen.actorlib import structuring, dma_asmi, spi

from milkymist.dvisampler.common import frame_layout

class DMA(Module):
	def __init__(self, asmiport):
		self.frame = Sink(frame_layout)
		self.shoot = CSR()

		###

		sof = Signal()
		parity_r = Signal()
		self.comb += sof.eq(self.frame.stb & (parity_r ^ self.frame.payload.parity))
		self.sync += If(self.frame.stb & self.frame.ack, parity_r.eq(self.frame.payload.parity))

		pending = Signal()
		frame_en = Signal()
		self.sync += [
			If(sof,
				frame_en.eq(0),
				If(pending, frame_en.eq(1)),
				pending.eq(0)
			),
			If(self.shoot.re, pending.eq(1))
		]

		pack_factor = asmiport.hub.dw//32
		self.submodules.packer = structuring.Pack(list(reversed([("pad", 2), ("r", 10), ("g", 10), ("b", 10)])), pack_factor)
		self.submodules.cast = structuring.Cast(self.packer.source.payload.layout, asmiport.hub.dw, reverse_from=False)
		self.submodules.dma = spi.DMAWriteController(dma_asmi.Writer(asmiport), spi.MODE_EXTERNAL)
		self.comb += [
			self.dma.generator.trigger.eq(self.shoot.re),
			self.packer.sink.stb.eq(self.frame.stb & frame_en),
			self.frame.ack.eq(self.packer.sink.ack | (~frame_en & ~(pending & sof))),
			self.packer.sink.payload.r.eq(self.frame.payload.r << 2),
			self.packer.sink.payload.g.eq(self.frame.payload.g << 2),
			self.packer.sink.payload.b.eq(self.frame.payload.b << 2),
			self.packer.source.connect(self.cast.sink, match_by_position=True),
			self.cast.source.connect(self.dma.data, match_by_position=True)
		]

	def get_csrs(self):
		return [self.shoot] + self.dma.get_csrs()
