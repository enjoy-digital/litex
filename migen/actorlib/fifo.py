from migen.fhdl.std import *
from migen.flow.actor import *
from migen.genlib import fifo

class _FIFOActor(Module):
	def __init__(self, fifo_class, layout, depth):
		self.sink = Sink(layout)
		self.source = Source(layout)
		self.busy = Signal()

		###

		description = self.sink.description
		fifo_layout = [
			("payload", description.payload_layout),
			# Note : Can be optimized by passing parameters
			#        in another fifo. We will only have one
			#        data per packet.
			("param", description.param_layout)
		]
		if description.packetized:
			fifo_layout += [("sop", 1), ("eop", 1)]

		self.submodules.fifo = fifo_class(fifo_layout, depth)

		self.comb += [
			self.sink.ack.eq(self.fifo.writable),
			self.fifo.we.eq(self.sink.stb),
			self.fifo.din.payload.eq(self.sink.payload),
			self.fifo.din.param.eq(self.sink.param),

			self.source.stb.eq(self.fifo.readable),
			self.source.payload.eq(self.fifo.dout.payload),
			self.source.param.eq(self.fifo.dout.param),
			self.fifo.re.eq(self.source.ack)
		]
		if description.packetized:
			self.comb += [
				self.fifo.din.sop.eq(self.sink.sop),
				self.fifo.din.eop.eq(self.sink.eop),
				self.source.sop.eq(self.fifo.dout.sop),
				self.source.eop.eq(self.fifo.dout.eop)
			]

class SyncFIFO(_FIFOActor):
	def __init__(self, layout, depth, buffered=False):
		_FIFOActor.__init__(
			self,
			fifo.SyncFIFOBuffered if buffered else fifo.SyncFIFO,
			layout, depth)

class AsyncFIFO(_FIFOActor):
	def __init__(self, layout, depth):
		_FIFOActor.__init__(self, fifo.AsyncFIFO, layout, depth)
