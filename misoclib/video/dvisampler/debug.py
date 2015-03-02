from migen.fhdl.std import *
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.record import layout_len
from migen.bank.description import AutoCSR
from migen.actorlib import structuring, spi

from misoclib.mem.sdram.frontend import dma_lasmi
from misoclib.video.dvisampler.edid import EDID
from misoclib.video.dvisampler.clocking import Clocking
from misoclib.video.dvisampler.datacapture import DataCapture

class RawDVISampler(Module, AutoCSR):
	def __init__(self, pads, asmiport):
		self.submodules.edid = EDID(pads)
		self.submodules.clocking = Clocking(pads)

		invert = False
		try:
			s = getattr(pads, "data0")
		except AttributeError:
			s = getattr(pads, "data0_n")
			invert = True
		self.submodules.data0_cap = DataCapture(8, invert)
		self.comb += [
			self.data0_cap.pad.eq(s),
			self.data0_cap.serdesstrobe.eq(self.clocking.serdesstrobe)
		]

		fifo = RenameClockDomains(AsyncFIFO(10, 256),
			{"write": "pix", "read": "sys"})
		self.submodules += fifo
		self.comb += [
			fifo.din.eq(self.data0_cap.d),
			fifo.we.eq(1)
		]

		pack_factor = asmiport.hub.dw//16
		self.submodules.packer = structuring.Pack([("word", 10), ("pad", 6)], pack_factor)
		self.submodules.cast = structuring.Cast(self.packer.source.payload.layout, asmiport.hub.dw)
		self.submodules.dma = spi.DMAWriteController(dma_lasmi.Writer(lasmim), spi.MODE_SINGLE_SHOT)
		self.comb += [
			self.packer.sink.stb.eq(fifo.readable),
			fifo.re.eq(self.packer.sink.ack),
			self.packer.sink.word.eq(fifo.dout),
			self.packer.source.connect_flat(self.cast.sink),
			self.cast.source.connect_flat(self.dma.data)
		]
