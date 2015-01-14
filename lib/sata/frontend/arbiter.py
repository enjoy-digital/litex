from lib.sata.common import *
from lib.sata.frontend.common import *

from migen.genlib.roundrobin import *

class SATAArbiter(Module):
	def __init__(self, slaves, master):
		if len(slaves) == 1:
			self.comb += slaves[0].connect(master)
		else:
			self.rr = RoundRobin(len(slaves))
			self.grant = self.rr.grant
			cases = {}
			for i, slave in enumerate(slaves):
				sink, source = slave.sink, slave.source
				start = Signal()
				done = Signal()
				ongoing = Signal()
				self.comb += [
					start.eq(sink.stb & sink.sop),
					done.eq(source.stb & source.last & source.eop & source.ack)
				]
				self.sync += \
					If(start,
						ongoing.eq(1)
					).Elif(done,
						ongoing.eq(0)
					)
				self.comb += self.rr.request[i].eq((start | ongoing) & ~done)
				cases[i] = [slaves[i].connect(master)]
			self.comb += Case(self.grant, cases)
