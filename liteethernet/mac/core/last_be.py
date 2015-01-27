from migen.fhdl.std import *
from migen.genlib.record import *
from migen.flow.actor import Sink, Source

from misoclib.ethmac.common import *

class TXLastBE(Module):
	def __init__(self, d_w):
		self.sink = sink = Sink(eth_description(d_w))
		self.source = source = Source(eth_description(d_w))

		###

		ongoing = Signal()
		self.sync += \
			If(self.sink.stb & self.sink.ack,
				If(sink.sop,
					ongoing.eq(1)
				).Elif(sink.last_be,
					ongoing.eq(0)
				)
			)
		self.comb += [
			Record.connect(self.sink, self.source),
			self.source.eop.eq(self.sink.last_be),
			self.source.stb.eq(self.sink.stb & (self.sink.sop | ongoing))
		]

class RXLastBE(Module):
	def __init__(self, d_w):
		self.sink = sink = Sink(eth_description(d_w))
		self.source = source = Source(eth_description(d_w))

		###

		self.comb += [
			Record.connect(self.sink, self.source),
			self.source.last_be.eq(self.sink.eop)
		]
