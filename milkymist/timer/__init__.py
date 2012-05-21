from migen.fhdl.structure import *
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.bank import csrgen

class Timer:
	def __init__(self, address, width=32):
		self._en = RegisterField("en")
		self._value = RegisterField("value", width, access_dev=READ_WRITE)
		self._reload = RegisterField("reload", width)
		regs = [self._en, self._value, self._reload]
		
		self.event = EventSourceLevel()
		self.events = EventManager(self.event)
		
		self.bank = csrgen.Bank(regs + self.events.get_registers(), address=address)

	def get_fragment(self):
		comb = [
			If(self._value.field.r == 0,
				self._value.field.w.eq(self._reload.field.r)
			).Else(
				self._value.field.w.eq(self._value.field.r - 1)
			),
			self._value.field.we.eq(self._en.field.r),
			self.event.trigger.eq(self._value.field.r != 0)
		]
		return Fragment(comb) \
			+ self.events.get_fragment() \
			+ self.bank.get_fragment()
