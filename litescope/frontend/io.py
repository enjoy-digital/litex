from migen.fhdl.structure import *
from migen.bank.description import *

class LiteScopeIO(Module, AutoCSR):
	def __init__(self, width):
		self._r_i = CSRStatus(width)
		self._r_o = CSRStorage(width)

		self.i = self._r_i.status
		self.o = self._r_o.storage
