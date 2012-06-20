from migen.fhdl.structure import *
from migen.flow.actor import *

class Cast(CombinatorialActor):
	def __init__(self, layout_from, layout_to):
		super().__init__(
			("sink", Sink, layout_from),
			("source", Source, layout_to))
	
	def get_process_fragment(self):
		sigs_from = self.token("sink").flatten()
		sigs_to = self.token("source").flatten()
		if sum(len(s) for s in sigs_from) != sum(len(s) for s in sigs_to):
			raise TypeError
		return Fragment([
			Cat(*sigs_to).eq(Cat(*sigs_from))
		])

class Chop(Actor):
	def __init__(self, n, layout_to):
		self.n = n
		layout_from = [("chunk{0}".format(i), layout_to)
			for i in range(self.n)]
		super().__init__(
			("sink", Sink, layout_from),
			("source", Source, layout_to))
	
	def get_fragment(self):
		muxbits = bits_for(self.n-1)
		mux = Signal(BV(muxbits))
		last = Signal()
		comb = [
			last.eq(mux == (self.n-1)),
			self.endpoints["source"].stb.eq(self.endpoints["sink"].stb),
			self.endpoints["sink"].ack.eq(last & self.endpoints["source"].ack)
		]
		sync = [
			If(self.endpoints["source"].stb & self.endpoints["source"].ack,
				If(last,
					mux.eq(0)
				).Else(
					mux.eq(mux + 1)
				)
			)
		]
		cases = [(Constant(i, BV(muxbits)),
			Cat(*self.token("source").flatten()).eq(*self.token("sink").subrecord("chunk{0}".format(i)).flatten()))
			for i in range(self.n)]
		cases[-1][0] = Default()
		comb.append(Case(mux, *cases))
		return Fragment(comb, sync)

class Pack(Actor):
	def __init__(self, layout_from, n):
		self.n = n
		layout_to = [("chunk{0}".format(i), layout_from)
			for i in range(self.n)]
		super().__init__(
			("sink", Sink, layout_from),
			("source", Source, layout_to))
	
	def get_fragment(self):
		demuxbits = bits_for(self.n-1)
		demux = Signal(BV(demuxbits))
		
		load_part = Signal()
		strobe_all = Signal()
		cases = [(Constant(i, BV(demuxbits)),
			Cat(*self.token("source").subrecord("chunk{0}".format(i)).flatten()).eq(*self.token("sink").flatten())
			for i in range(self.n)]
		comb = [
			self.endpoints["sink"].ack.eq(~strobe_all | self.endpoints["source"].ack),
			self.endpoints["source"].stb.eq(strobe_all),
			load_part.eq(self.endpoints["sink"].stb & self.endpoints["sink"].ack)
		]
		sync = [
			If(self.endpoints["source"].ack,
				strobe_all.eq(0)
			),
			If(load_part,
				Case(demux, *cases),
				If(demux == (self.n - 1),
					demux.eq(0),
					strobe_all.eq(1)
				).Else(
					demux.eq(demux + 1)
				)
			)
		]
		return Fragment(comb, sync)
