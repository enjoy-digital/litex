from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *

from milkymist.dvisampler.edid import EDID
from milkymist.dvisampler.clocking import Clocking
from milkymist.dvisampler.datacapture import DataCapture

class DVISampler(Module, AutoReg):
	def __init__(self, inversions="", debug_data_capture=True):
		self.submodules.edid = EDID()
		self.sda = self.edid.sda
		self.scl = self.edid.scl

		self.submodules.clocking = Clocking()
		self.clk = self.clocking.clkin

		for datan in "012":
			name = "data" + str(datan)
			cap = DataCapture(8, debug_data_capture)
			setattr(self.submodules, name + "_cap", cap)
			if datan in inversions:
				name += "_n"
			s = Signal(name=name)
			setattr(self, name, s)
			self.comb += [
				cap.pad.eq(s),
				cap.serdesstrobe.eq(self.clocking.serdesstrobe)
			]
