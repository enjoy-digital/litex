from migen.fhdl.structure import *
from migen.corelogic.record import *
from migen.corelogic.fsm import *
from migen.flow.actor import *

# Generates integers from start to maximum-1
class IntSequence(Actor):
	def __init__(self, nbits, offsetbits=0, step=1):
		self.nbits = nbits
		self.offsetbits = offsetbits
		self.step = step
		
		parameters_layout = [("maximum", self.nbits)]
		if self.offsetbits:
			parameters_layout.append(("offset", self.offsetbits))
		
		Actor.__init__(self,
			("parameters", Sink, parameters_layout),
			("source", Source, [("value", max(self.nbits, self.offsetbits))]))
	
	def get_fragment(self):
		load = Signal()
		ce = Signal()
		last = Signal()
		
		maximum = Signal(self.nbits)
		if self.offsetbits:
			offset = Signal(self.offsetbits)
		counter = Signal(self.nbits)
		
		if self.step > 1:
			comb = [last.eq(counter + self.step >= maximum)]
		else:
			comb = [last.eq(counter + 1 == maximum)]
		sync = [
			If(load,
				counter.eq(0),
				maximum.eq(self.token("parameters").maximum),
				offset.eq(self.token("parameters").offset) if self.offsetbits else None
			).Elif(ce,
				If(last,
					counter.eq(0)
				).Else(
					counter.eq(counter + self.step)
				)
			)
		]
		if self.offsetbits:
			comb.append(self.token("source").value.eq(counter + offset))
		else:
			comb.append(self.token("source").value.eq(counter))
		counter_fragment = Fragment(comb, sync)
		
		fsm = FSM("IDLE", "ACTIVE")
		fsm.act(fsm.IDLE,
			load.eq(1),
			self.endpoints["parameters"].ack.eq(1),
			If(self.endpoints["parameters"].stb, fsm.next_state(fsm.ACTIVE))
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
