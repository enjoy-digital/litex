from migen.fhdl.std import *
from migen.bank.description import AutoCSR

from milkymist.dvisampler.edid import EDID
from milkymist.dvisampler.clocking import Clocking
from milkymist.dvisampler.datacapture import DataCapture
from milkymist.dvisampler.charsync import CharSync
from milkymist.dvisampler.wer import WER
from milkymist.dvisampler.decoding import Decoding
from milkymist.dvisampler.chansync import ChanSync
from milkymist.dvisampler.analysis import SyncPolarity, ResolutionDetection, FrameExtraction
from milkymist.dvisampler.dma import DMA

class DVISampler(Module, AutoCSR):
	def __init__(self, pads, asmiport, n_dma_slots=2):
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

			wer = WER()
			setattr(self.submodules, name + "_wer", wer)
			self.comb += wer.data.eq(charsync.data)

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

		###

		self.submodules.syncpol = SyncPolarity()
		self.comb += [
			self.syncpol.valid_i.eq(self.chansync.chan_synced),
			self.syncpol.data_in0.eq(self.chansync.data_out0),
			self.syncpol.data_in1.eq(self.chansync.data_out1),
			self.syncpol.data_in2.eq(self.chansync.data_out2)
		]

		self.submodules.resdetection = ResolutionDetection()
		self.comb += [
			self.resdetection.valid_i.eq(self.syncpol.valid_o),
			self.resdetection.de.eq(self.syncpol.de),
			self.resdetection.vsync.eq(self.syncpol.vsync)
		]

		self.submodules.frame = FrameExtraction()
		self.comb += [
			self.frame.valid_i.eq(self.syncpol.valid_o),
			self.frame.de.eq(self.syncpol.de),
			self.frame.vsync.eq(self.syncpol.vsync),
			self.frame.r.eq(self.syncpol.r),
			self.frame.g.eq(self.syncpol.g),
			self.frame.b.eq(self.syncpol.b)
		]

		self.submodules.dma = DMA(asmiport, n_dma_slots)
		self.comb += self.frame.frame.connect(self.dma.frame)
		self.ev = self.dma.ev

	autocsr_exclude = {"ev"}
