from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import csrgen
from migen.bank.description import *

class MiIo(Module, AutoCSR):
	def __init__(self, width):
		self.width = width

		self.i = Signal(self.width)
		self.o = Signal(self.width)

		self._r_i = CSRStatus(self.width)
		self._r_o = CSRStorage(self.width)

		self.sync +=[
			self._r_i.status.eq(self.i),
			self.o.eq(self._r_o.storage)
		]