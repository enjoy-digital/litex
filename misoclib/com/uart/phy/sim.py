from migen.fhdl.std import *
from migen.flow.actor import Sink, Source

class UARTPHYSim(Module):
	def __init__(self, pads):
		self.dw = 8
		self.tuning_word = Signal(32)
		self.sink = Sink([("d", 8)])
		self.source = Source([("d", 8)])

		self.comb += [
			pads.source_stb.eq(self.sink.stb),
			pads.source_d.eq(self.sink.d),
			self.sink.ack.eq(pads.source_ack),

			self.source.stb.eq(pads.sink_stb),
			self.source.d.eq(pads.sink_d)
		]
