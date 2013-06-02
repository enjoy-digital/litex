from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import csrgen
from migen.bank.description import *

from miscope.tools.misc import *

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
			self._r_i = CSRStatus(self.width)
			
		if "O" in self.mode:
			self.o = Signal(self.width)
			self._r_o = CSRStorage(self.width)
			
		self.bank = csrgen.Bank([self._r_o, self._r_i], address=self.address)
		
	def get_fragment(self):
		comb = []
		
		if "I" in self.mode:
			comb += [self._r_i.status.eq(self.i)]
			
		if "O" in self.mode:
			comb += [self.o.eq(self._r_o.storage)]
			
		return Fragment(comb) + self.bank.get_fragment()
	#
	# Driver
	#
	def set(self, data):
			self.interface.write(get_csr_base(self.bank), data)
			
	def get(self):
		return self.interface.read(get_csr_base(self.bank) + self.words)