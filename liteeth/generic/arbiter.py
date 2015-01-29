from migen.fhdl.std import *
from migen.genlib.roundrobin import *
from migen.genlib.record import *

class Arbiter(Module):
	def __init__(self, sources, sink):
		if len(sources) == 0:
			pass
		elif len(sources) == 1:
			self.grant = Signal()
			self.comb += Record.connect(sources[0], sink)
		else:
			self.rr = RoundRobin(len(sources))
			self.grant = self.rr.grant
			cases = {}
			for i, source in enumerate(sources):
				sop = Signal()
				eop = Signal()
				ongoing = Signal()
				self.comb += [
					sop.eq(source.stb & source.sop),
					eop.eq(source.stb & source.eop & source.ack),
				]
				self.sync += ongoing.eq((sop | ongoing) & ~eop)
				self.comb += self.rr.request[i].eq((sop | ongoing) & ~eop)
				cases[i] = [Record.connect(source, sink)]
			self.comb += Case(self.grant, cases)
