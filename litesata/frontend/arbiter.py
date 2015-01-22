from litesata.common import *
from litesata.frontend.common import *

from migen.genlib.roundrobin import *

class LiteSATAArbiter(Module):
	def __init__(self, users, master):
		self.rr = RoundRobin(len(users))
		self.grant = self.rr.grant
		cases = {}
		for i, slave in enumerate(users):
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
			cases[i] = [users[i].connect(master)]
		self.comb += Case(self.grant, cases)
