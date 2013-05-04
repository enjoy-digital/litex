from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *
from migen.genlib.fifo import AsyncFIFO
from migen.actorlib import structuring, dma_asmi, spi

from milkymist.dvisampler.edid import EDID
from milkymist.dvisampler.clocking import Clocking
from milkymist.dvisampler.datacapture import DataCapture
from milkymist.dvisampler.charsync import CharSync
from milkymist.dvisampler.decoding import Decoding
from milkymist.dvisampler.chansync import ChanSync
from milkymist.dvisampler.resdetection import ResolutionDetection

class DVISampler(Module, AutoCSR):
	def __init__(self, pads):
		self.submodules.edid = EDID(pads)
		self.submodules.clocking = Clocking(pads)

		for datan in range(3):
			name = "data" + str(datan)
			invert = False
			try:
				s = getattr(pads, name)
			except AttributeError:
				s = getattr(pads, name + "_n")
				invert = True
			
			cap = DataCapture(8, invert)
			setattr(self.submodules, name + "_cap", cap)
			self.comb += [
				cap.pad.eq(s),
				cap.serdesstrobe.eq(self.clocking.serdesstrobe)
			]

			charsync = CharSync()
			setattr(self.submodules, name + "_charsync", charsync)
			self.comb += charsync.raw_data.eq(cap.d)

			decoding = Decoding()
			setattr(self.submodules, name + "_decod", decoding)
			self.comb += [
				decoding.valid_i.eq(charsync.synced),
				decoding.input.eq(charsync.data)
			]

		self.submodules.chansync = ChanSync()
		self.comb += [
			self.chansync.valid_i.eq(self.data0_decod.valid_o & \
			  self.data1_decod.valid_o & self.data2_decod.valid_o),
			self.chansync.data_in0.eq(self.data0_decod.output),
			self.chansync.data_in1.eq(self.data1_decod.output),
			self.chansync.data_in2.eq(self.data2_decod.output),
		]

		de = self.chansync.data_out0.de
		r = self.chansync.data_out2.d
		g = self.chansync.data_out1.d
		b = self.chansync.data_out0.d
		hsync = self.chansync.data_out0.c[0]
		vsync = self.chansync.data_out0.c[1]

		self.submodules.resdetection = ResolutionDetection()
		self.comb += [
			self.resdetection.de.eq(de),
			self.resdetection.hsync.eq(hsync),
			self.resdetection.vsync.eq(vsync)
		]

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

		fifo = AsyncFIFO(10, 1024)
		self.add_submodule(fifo, {"write": "pix", "read": "sys"})
		self.comb += [
			fifo.din.eq(self.data0_cap.d),
			fifo.we.eq(1)
		]

		pack_factor = asmiport.hub.dw//16
		self.submodules.packer = structuring.Pack([("word", 10), ("pad", 6)], pack_factor)
		self.submodules.cast = structuring.Cast(self.packer.source.payload.layout, asmiport.hub.dw)
		self.submodules.dma = spi.DMAWriteController(dma_asmi.Writer(asmiport), spi.MODE_SINGLE_SHOT)
		self.comb += [
			self.packer.sink.stb.eq(fifo.readable),
			fifo.re.eq(self.packer.sink.ack),
			self.packer.sink.payload.word.eq(fifo.dout),
			self.packer.source.connect(self.cast.sink, match_by_position=True),
			self.cast.source.connect(self.dma.data, match_by_position=True)
		]
