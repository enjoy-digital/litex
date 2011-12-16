from migen.fhdl.structure import *

class Inst:
	def __init__(self, trigger, events):
		self.trigger = trigger
		self.events = events
		self.lastevent = max([e[0] for e in events])
		declare_signal(self, "_counter", BV(bits_for(self.lastevent)))
	
	def get_fragment(self):
		counterlogic = If(self._counter != Constant(0, self._counter.bv),
			self._counter.eq(self._counter + Constant(1, self._counter.bv))
		).Elif(self.trigger,
			self._counter.eq(Constant(1, self._counter.bv))
		)
		# insert counter reset if it doesn't automatically overflow
		# (test if self.lastevent+1 is a power of 2)
		if (self.lastevent & (self.lastevent + 1)) != 0:
			counterlogic = If(self._counter == self.lastevent,
				self._counter.eq(Constant(0, self._counter.bv))
			).Else(
				counterlogic
			)
		def get_cond(e):
			if e[0] == 0:
				return self.trigger & (self._counter == Constant(0, self._counter.bv))
			else:
				return self._counter == Constant(e[0], self._counter.bv)
		sync = [If(get_cond(e), *e[1]) for e in self.events]
		sync.append(counterlogic)
		return Fragment(sync=sync)
