from migen.fhdl.std import *
from migen.flow.actor import Sink, Source

class UARTPHYSim(Module):
	def __init__(self, pads):
		self.sink = Sink([("data", 8)])
		self.source = Source([("data", 8)])

		self.comb += [
			pads.source_stb.eq(self.sink.stb),
			pads.source_data.eq(self.sink.data),
			self.sink.ack.eq(pads.source_ack),

			self.source.stb.eq(pads.sink_stb),
			self.source.data.eq(pads.sink_data),
			pads.sink_ack.eq(self.source.ack)
		]
