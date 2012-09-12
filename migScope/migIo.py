from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *


class MigIo:
	def __init__(self, width, mode = "IO"):
		self.width = width
		self.mode = mode
		self.ireg = description.RegisterField("i", 0, READ_ONLY, WRITE_ONLY)
		self.oreg = description.RegisterField("o", 0)
		if "I" in self.mode:
			self.i = Signal(BV(self.width))
			self.ireg = description.RegisterField("i", self.width, READ_ONLY, WRITE_ONLY)
			self.ireg.field.w.name_override = "inputs"
		if "O" in self.mode:
			self.o = Signal(BV(self.width))
			self.oreg = description.RegisterField("o", self.width)
			self.oreg.field.r.name_override = "ouptuts"
		self.bank = csrgen.Bank([self.oreg, self.ireg])

	def get_fragment(self):
		comb = []
		comb += [self.ireg.field.w.eq(self.i)]
		comb += [self.o.eq(self.oreg.field.r)]		
		return Fragment(comb=comb) + self.bank.get_fragment()
