from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *


class MigIo:
	def __init__(self,address, width, mode = "IO", interface=None):
		self.address = address
		self.width = width
		self.mode = mode
		self.interface = interface
		self.words = int(2**bits_for(width-1)/8)
		if "I" in self.mode:
			self.i = Signal(BV(self.width))
			self.ireg = description.RegisterField("i", self.width, READ_ONLY, WRITE_ONLY)
			self.ireg.field.w.name_override = "inputs"
		if "O" in self.mode:
			self.o = Signal(BV(self.width))
			self.oreg = description.RegisterField("o", self.width)
			self.oreg.field.r.name_override = "ouptuts"
		self.bank = csrgen.Bank([self.oreg, self.ireg], address=self.address)
	
	def write(self, data):
			self.interface.write_n(self.address, data, self.width)
			
	def read(self):
		r = 0
			r = self.interface.read_n(self.address + self.words, self.width)
		return r
				
	def get_fragment(self):
		comb = []
		if "I" in self.mode:
			comb += [self.ireg.field.w.eq(self.i)]
		if "O" in self.mode:
			comb += [self.o.eq(self.oreg.field.r)]
		return Fragment(comb=comb) + self.bank.get_fragment()
