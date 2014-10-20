from migen.fhdl.std import *
from migen.genlib.record import *
from migen.genlib.fsm import *
from migen.flow.actor import *

# Generates integers from start to maximum-1
class IntSequence(Module):
	def __init__(self, nbits, offsetbits=0, step=1):
		parameters_layout = [("maximum", nbits)]
		if offsetbits:
			parameters_layout.append(("offset", offsetbits))

		self.parameters = Sink(parameters_layout)
		self.source = Source([("value", max(nbits, offsetbits))])
		self.busy = Signal()

		###

		load = Signal()
		ce = Signal()
		last = Signal()

		maximum = Signal(nbits)
		if offsetbits:
			offset = Signal(offsetbits)
		counter = Signal(nbits)

		if step > 1:
			self.comb += last.eq(counter + step >= maximum)
		else:
			self.comb += last.eq(counter + 1 == maximum)
		self.sync += [
			If(load,
				counter.eq(0),
				maximum.eq(self.parameters.maximum),
				offset.eq(self.parameters.offset) if offsetbits else None
			).Elif(ce,
				If(last,
					counter.eq(0)
				).Else(
					counter.eq(counter + step)
				)
			)
		]
		if offsetbits:
			self.comb += self.source.value.eq(counter + offset)
		else:
			self.comb += self.source.value.eq(counter)

		fsm = FSM()
		self.submodules += fsm
		fsm.act("IDLE",
			load.eq(1),
			self.parameters.ack.eq(1),
			If(self.parameters.stb, NextState("ACTIVE"))
		)
		fsm.act("ACTIVE",
			self.busy.eq(1),
			self.source.stb.eq(1),
			If(self.source.ack,
				ce.eq(1),
				If(last, NextState("IDLE"))
			)
		)
