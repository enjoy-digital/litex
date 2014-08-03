from migen.fhdl.structure import *
from migen.bank.description import *

class MiIo(Module, AutoCSR):
	def __init__(self, width):
		self.width = width

		self.i = Signal(width)
		self.o = Signal(width)

		self._r_i = CSRStatus(width)
		self._r_o = CSRStorage(width)

		self.sync += [
			self._r_i.status.eq(self.i),
			self.o.eq(self._r_o.storage)
		]
