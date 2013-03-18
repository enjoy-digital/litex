from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *

class MiIo:
	# 
	# Definition
	#
	def __init__(self, address, width, mode="IO", interface=None):
		self.address = address
		self.width = width
		self.mode = mode.upper()
		self.interface = interface
		self.words = int((2**bits_for(width-1))/8)
		
		if "I" in self.mode:
			self.i = Signal(self.width)
			self.ireg = description.RegisterField("i", self.width, READ_ONLY, WRITE_ONLY)
			
		if "O" in self.mode:
			self.o = Signal(self.width)
			self.oreg = description.RegisterField("o", self.width)
			
		self.bank = csrgen.Bank([self.oreg, self.ireg], address=self.address)
		
	def get_fragment(self):
		comb = []
		
		if "I" in self.mode:
			comb += [self.ireg.field.w.eq(self.i)]
			
		if "O" in self.mode:
			comb += [self.o.eq(self.oreg.field.r)]
			
		return Fragment(comb) + self.bank.get_fragment()
	#
	#Driver
	#
	def write(self, data):
			self.interface.write(self.address, data)
			
	def read(self):
		return self.interface.read(self.address + self.words)