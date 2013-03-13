from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *

from milkymist.dvisampler.edid import EDID

class DVISampler(Module, AutoReg):
	def __init__(self, inversions=""):
		self.clk = Signal()
		for datan in "012":
			name = "data" + str(datan)
			if datan in inversions:
				name += "_n"
			setattr(self, name, Signal(name=name))
		
		self.submodules.edid = EDID()
		self.sda = self.edid.sda
		self.scl = self.edid.scl
