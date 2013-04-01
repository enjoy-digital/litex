from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.flow.actor import *
from migen.genlib.record import *
from migen.genlib.misc import optree

class Buffer(PipelinedActor):
	def __init__(self, layout):
		PipelinedActor.__init__(self, 1,
			("d", Sink, layout), ("q", Source, layout))
	
	def get_process_fragment(self):
		sigs_d = self.token("d").flatten()
		sigs_q = self.token("q").flatten()
		sync = [If(self.pipe_ce, Cat(*sigs_q).eq(Cat(*sigs_d)))]
		return Fragment(sync=sync)

class Combinator(Module, Actor):
	def __init__(self, layout, subrecords):
		eps = [("source", Source, layout)]
		eps += [("sink"+str(n), Sink, layout_partial(layout, r))
			for n, r in enumerate(subrecords)]
		Actor.__init__(self, *eps)

		###
	
		source = self.endpoints["source"]
		sinks = [self.endpoints["sink"+str(n)]
			for n in range(len(self.endpoints)-1)]
		self.comb += [source.stb.eq(optree("&", [sink.stb for sink in sinks]))]
		self.comb += [sink.ack.eq(source.ack & source.stb) for sink in sinks]
		self.comb += [source.token.eq(sink.token) for sink in sinks]

class Splitter(Module, Actor):
	def __init__(self, layout, subrecords):
		eps = [("sink", Sink, layout)]
		eps += [("source"+str(n), Source, layout_partial(layout, *r))
			for n, r in enumerate(subrecords)]
		Actor.__init__(self, *eps)
		
		###

		sources = [self.endpoints[e] for e in self.sources()]
		sink = self.endpoints[self.sinks()[0]]

		self.comb += [source.token.eq(sink.token) for source in sources]
		
		already_acked = Signal(len(sources))
		self.sync += If(sink.stb,
				already_acked.eq(already_acked | Cat(*[s.ack for s in sources])),
				If(sink.ack, already_acked.eq(0))
			)
		self.comb += sink.ack.eq(optree("&",
				[s.ack | already_acked[n] for n, s in enumerate(sources)]))
		for n, s in enumerate(sources):
			self.comb += s.stb.eq(sink.stb & ~already_acked[n])

# Actors whose layout should be inferred from what their single sink is connected to.
layout_sink = {Buffer, Splitter}
# Actors whose layout should be inferred from what their single source is connected to.
layout_source = {Buffer, Combinator}
# All actors.
actors = layout_sink | layout_source
