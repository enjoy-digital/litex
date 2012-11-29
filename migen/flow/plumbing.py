from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.corelogic.record import *
from migen.corelogic.misc import optree

class Buffer(PipelinedActor):
	def __init__(self, layout):
		super().__init__(1,
			("d", Sink, layout), ("q", Source, layout))
	
	def get_process_fragment(self):
		sigs_d = self.token("d").flatten()
		sigs_q = self.token("q").flatten()
		sync = [If(self.pipe_ce, Cat(*sigs_q).eq(Cat(*sigs_d)))]
		return Fragment(sync=sync)

class Combinator(Actor):
	def __init__(self, layout, subrecords):
		source = Record(layout)
		subrecords = [source.subrecord(*subr) for subr in subrecords]
		eps = [("sink{0}".format(n), Sink, r)
			for n, r in enumerate(subrecords)]
		ep_source = ("source", Source, source)
		eps.append(ep_source)
		super().__init__(*eps)

	def get_fragment(self):
		source = self.endpoints["source"]
		sinks = [self.endpoints["sink{0}".format(n)]
			for n in range(len(self.endpoints)-1)]
		comb = [source.stb.eq(optree("&", [sink.stb for sink in sinks]))]
		comb += [sink.ack.eq(source.ack & source.stb) for sink in sinks]
		return Fragment(comb)

class Splitter(Actor):
	def __init__(self, layout, subrecords):
		sink = Record(layout)
		subr = []
		for s in subrecords:
			if s is None:
				subr.append(sink)
			else:
				subr.append(sink.subrecord(*s))
		eps = [("source{0}".format(n), Source, r)
			for n, r in enumerate(subr)]
		ep_sink = ("sink", Sink, sink)
		eps.append(ep_sink)
		super().__init__(*eps)
		
	def get_fragment(self):
		sources = [self.endpoints[e] for e in self.sources()]
		sink = self.endpoints[self.sinks()[0]]
		
		already_acked = Signal(len(sources))
		sync = [
			If(sink.stb,
				already_acked.eq(already_acked | Cat(*[s.ack for s in sources])),
				If(sink.ack, already_acked.eq(0))
			)
		]
		comb = [
			sink.ack.eq(optree("&",
				[s.ack | already_acked[n] for n, s in enumerate(sources)]))
		]
		for n, s in enumerate(sources):
			comb.append(s.stb.eq(sink.stb & ~already_acked[n]))
		return Fragment(comb, sync)

# Actors whose layout should be inferred from what their single sink is connected to.
layout_sink = {Buffer, Splitter}
# Actors whose layout should be inferred from what their single source is connected to.
layout_source = {Buffer, Combinator}
# All actors.
actors = layout_sink | layout_source
