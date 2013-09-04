from migen.fhdl.std import *
from migen.flow.actor import *
from migen.genlib import fifo

class _FIFOActor(Module):
	def __init__(self, fifo_class, layout, depth):
		self.sink = Sink(layout)
		self.source = Source(layout)
		self.busy = Signal()

		###

		self.submodules.fifo = fifo_class(layout, depth)

		self.comb += [
			self.sink.ack.eq(self.fifo.writable),
			self.fifo.we.eq(self.sink.stb & self.sink.ack),
			self.fifo.din.eq(self.sink.payload),

			self.source.stb.eq(self.fifo.readable),
			self.source.payload.eq(self.fifo.dout),
			self.fifo.re.eq(self.source.ack)
		]


class SyncFIFO(_FIFOActor):
	def __init__(self, layout, depth):
		_FIFOActor.__init__(self, fifo.SyncFIFO, layout, depth)

class AsyncFIFO(_FIFOActor):
	def __init__(self, layout, depth):
		_FIFOActor.__init__(self, fifo.AsyncFIFO, layout, depth)		
