from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *
from migen.bank.eventmanager import *

class Timer(Module, AutoCSR):
	def __init__(self, width=32):
		self._en = CSRStorage()
		self._value = CSRStorage(width, write_from_dev=True)
		self._reload = CSRStorage(width)
		
		self.submodules.ev = EventManager()
		self.ev.zero = EventSourceProcess()
		self.ev.finalize()

		###

		self.comb += [
			If(self._value.storage == 0,
				self._value.dat_w.eq(self._reload.storage)
			).Else(
				self._value.dat_w.eq(self._value.storage - 1)
			),
			self._value.we.eq(self._en.storage),
			self.ev.zero.trigger.eq(self._value.storage != 0)
		]
