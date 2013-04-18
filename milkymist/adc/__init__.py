from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *
from migen.genlib.misc import optree

class CounterADC(Module, AutoCSR):
	def __init__(self, charge, sense, width = 24):
		if not isinstance(sense, collections.Iterable):
			sense = [sense]

		channels = len(sense)

		self._start_busy = CSR()
		self._overflow = CSRStatus(channels)
		self._polarity = CSRStorage()

		count = Signal(width)
		busy = Signal(channels)

		res = []
		for i in range(channels):
			res.append(CSRStatus(width, name="res"+str(i)))
			setattr(self, "_res"+str(i), res[-1])

		any_busy = Signal()
		self.comb += [
			any_busy.eq(optree("|",
			    [busy[i] for i in range(channels)])),
			self._start_busy.w.eq(any_busy)
		]

		carry = Signal()

		self.sync += [
			If(self._start_busy.re,
				count.eq(0),
				busy.eq((1 << channels)-1),
				self._overflow.status.eq(0),
			    	charge.eq(~self._polarity.storage)
			).Elif(any_busy,
				Cat(count, carry).eq(count + 1),
				If(carry,
					self._overflow.status.eq(busy),
					busy.eq(0)
				)
			).Else(
				charge.eq(self._polarity.storage)
			)
		]

		for i in range(channels):
			self.sync += If(busy[i],
				If(sense[i] != self._polarity.storage,
					res[i].status.eq(count),
					busy[i].eq(0)
				)
			)
