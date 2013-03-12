from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *
from migen.bank.eventmanager import *

class Timer(Module, AutoReg):
	def __init__(self, width=32):
		self._en = RegisterField()
		self._value = RegisterField(width, access_dev=READ_WRITE)
		self._reload = RegisterField(width)
		
		self.submodules.ev = EventManager()
		self.ev.zero = EventSourceLevel()
		self.ev.finalize()

		###

		self.comb += [
			If(self._value.field.r == 0,
				self._value.field.w.eq(self._reload.field.r)
			).Else(
				self._value.field.w.eq(self._value.field.r - 1)
			),
			self._value.field.we.eq(self._en.field.r),
			self.ev.zero.trigger.eq(self._value.field.r != 0)
		]
