from migen.fhdl.structure import *
from migen.corelogic.record import *
from migen.corelogic.fsm import *
from migen.flow.actor import *

# Generates integers from start to maximum-1
class IntSequence(Actor):
	def __init__(self, nbits, step=1):
		self.nbits = nbits
		self.step = step
		
		super().__init__(
			("maximum", Sink, [("value", BV(nbits))]),
			("source", Source, [("value", BV(nbits))]))
	
	def get_fragment(self):
		load = Signal()
		ce = Signal()
		last = Signal()
		
		maximum = Signal(BV(self.nbits))
		counter = Signal(BV(self.nbits))
		
		if self.step > 1:
			comb = [last.eq(counter + self.step >= maximum)]
		else:
			comb = [last.eq(counter + 1 == maximum)]
		sync = [
			If(load,
				counter.eq(0),
				maximum.eq(self.token("maximum").value)
			).Elif(ce,
				If(last,
					counter.eq(0)
				).Else(
					counter.eq(counter + self.step)
				)
			)
		]
		comb.append(self.token("source").value.eq(counter))
		counter_fragment = Fragment(comb, sync)
		
		fsm = FSM("IDLE", "ACTIVE")
		fsm.act(fsm.IDLE,
			load.eq(1),
			self.endpoints["maximum"].ack.eq(1),
			If(self.endpoints["maximum"].stb, fsm.next_state(fsm.ACTIVE))
		)
		fsm.act(fsm.ACTIVE,
			self.busy.eq(1),
			self.endpoints["source"].stb.eq(1),
			If(self.endpoints["source"].ack,
				ce.eq(1),
				If(last, fsm.next_state(fsm.IDLE))
			)
		)
		return counter_fragment + fsm.get_fragment()
