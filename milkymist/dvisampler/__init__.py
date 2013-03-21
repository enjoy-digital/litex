from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *

from milkymist.dvisampler.edid import EDID
from milkymist.dvisampler.clocking import Clocking
from milkymist.dvisampler.datacapture import DataCapture
from milkymist.dvisampler.charsync import CharSync

class DVISampler(Module, AutoReg):
	def __init__(self, inversions=""):
		self.submodules.edid = EDID()
		self.sda = self.edid.sda
		self.scl = self.edid.scl

		self.submodules.clocking = Clocking()
		self.clk = self.clocking.clkin

		for datan in "012":
			name = "data" + str(datan)
			invert = datan in inversions
			
			signame = name + "_n" if invert else name
			s = Signal(name=signame)
			setattr(self, signame, s)

			cap = DataCapture(8, invert)
			setattr(self.submodules, name + "_cap", cap)
			self.comb += [
				cap.pad.eq(s),
				cap.serdesstrobe.eq(self.clocking.serdesstrobe)
			]

			charsync = CharSync()
			setattr(self.submodules, name + "_charsync", charsync)
			self.comb += charsync.raw_data.eq(cap.d)
