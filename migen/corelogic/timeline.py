from migen.fhdl import structure as f

class Inst:
	def __init__(self, trigger, events):
		self.trigger = trigger
		self.events = events
		self.lastevent = max([e[0] for e in events] + [e[2] for e in events if len(e) == 3])
		f.Declare(self, "_counter", f.BV(f.BitsFor(self.lastevent)))
	
	def GetFragment(self):
		counterlogic = f.If(self._counter != f.Constant(0, self._counter.bv), 
			[f.Assign(self._counter, self._counter + f.Constant(1, self._counter.bv))],
			[f.If(self.trigger, [f.Assign(self._counter, f.Constant(1, self._counter.bv))])])
		# insert counter reset if it doesn't automatically overflow
		# (test if self.lastevent+1 is a power of 2)
		if (self.lastevent & (self.lastevent + 1)) != 0:
			counterlogic = f.If(self._counter == self.lastevent,
				[f.Assign(self._counter, f.Constant(0, self._counter.bv))],
				[counterlogic])
		def getcond(e):
			if len(e) == 3:
				if e[0] == 0:
					return self.trigger & (self._counter <= f.Constant(e[2], self._counter.bv))
				else:
					return (self._counter >= f.Constant(e[0], self._counter.bv)) & (self._counter <= f.Constant(e[2], self._counter.bv))
			else:
				if e[0] == 0:
					return self.trigger
				else:
					return self._counter == f.Constant(e[0], self._counter.bv)
		sync = [f.If(getcond(e), e[1]) for e in self.events]
		sync.append(counterlogic)
		return f.Fragment(sync=sync)
