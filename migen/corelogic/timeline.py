from migen.fhdl.structure import *

class Timeline:
	def __init__(self, trigger, events):
		self.trigger = trigger
		self.events = events
		self.lastevent = max([e[0] for e in events])
	
	def get_fragment(self):
		counter = Signal(BV(bits_for(self.lastevent)))
		
		counterlogic = If(counter != Constant(0, counter.bv),
			counter.eq(counter + Constant(1, counter.bv))
		).Elif(self.trigger,
			counter.eq(Constant(1, counter.bv))
		)
		# insert counter reset if it doesn't automatically overflow
		# (test if self.lastevent+1 is a power of 2)
		if (self.lastevent & (self.lastevent + 1)) != 0:
			counterlogic = If(counter == self.lastevent,
				counter.eq(Constant(0, counter.bv))
			).Else(
				counterlogic
			)
		def get_cond(e):
			if e[0] == 0:
				return self.trigger & (counter == Constant(0, counter.bv))
			else:
				return counter == Constant(e[0], counter.bv)
		sync = [If(get_cond(e), *e[1]) for e in self.events]
		sync.append(counterlogic)
		return Fragment(sync=sync)
