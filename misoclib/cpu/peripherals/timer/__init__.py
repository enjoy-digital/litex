from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.misc import Counter

class Timer(Module, AutoCSR):
	def __init__(self, width=32, prescaler_width=32):
		self._load = CSRStorage(width)
		self._reload = CSRStorage(width)
		self._en = CSRStorage()
		self._prescaler = CSRStorage(prescaler_width, reset=1)
		self._update_value = CSR()
		self._value = CSRStatus(width)

		self.submodules.ev = EventManager()
		self.ev.zero = EventSourceProcess()
		self.ev.finalize()

		###
		enable = self._en.storage
		tick = Signal()

		counter = Counter(prescaler_width)
		self.submodules += counter
		self.comb += [
			If(enable,
				tick.eq(counter.value >= (self._prescaler.storage-1)),
				counter.ce.eq(1),
				counter.reset.eq(tick),
			).Else(
				counter.reset.eq(1)
			)
		]

		value = Signal(width)
		self.sync += [
			If(enable,
				If(value == 0,
					# set reload to 0 to disable reloading
					value.eq(self._reload.storage)
				).Elif(tick,
					value.eq(value - 1)
				)
			).Else(
				value.eq(self._load.storage)
			),
			If(self._update_value.re, self._value.status.eq(value))
		]
		self.comb += self.ev.zero.trigger.eq(value != 0)
