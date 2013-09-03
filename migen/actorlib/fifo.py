from migen.fhdl.std import *
from migen.flow.actor import *
from migen.genlib import fifo

def FIFOWrapper(sink, source, fifo):
	return [
			sink.ack.eq(fifo.writable),
			fifo.we.eq(sink.stb & sink.ack),
			fifo.din.eq(sink.payload),

			source.stb.eq(fifo.readable),
			source.payload.eq(fifo.dout),
			fifo.re.eq(source.ack)
	]

class SyncFIFO(Module):
	def __init__(self, layout, depth):

		self.sink = Sink(layout)
		self.source = Source(layout)
		self.busy = Signal()

		_fifo = fifo.SyncFIFO(layout, depth)		

		self.submodules += _fifo

		self.comb += FIFOWrapper(self.sink, self.source, _fifo)

class AsyncFIFO(Module):
	def __init__(self, layout, depth, cd_write="write", cd_read="read"):

		self.sink = Sink(layout)
		self.source = Source(layout)
		self.busy = Signal()

		_fifo = RenameClockDomains(fifo.AsyncFIFO(layout, depth),
			{"write": cd_write, "read": cd_read})
		self.submodules += _fifo

		self.comb += FIFOWrapper(self.sink, self.source, _fifo)
		