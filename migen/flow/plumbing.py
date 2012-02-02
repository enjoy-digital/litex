from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.corelogic.record import *
from migen.corelogic.misc import optree

class Buffer(Actor):
	def __init__(self, layout):
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.PIPELINE, 1),
			("d", Sink, layout), ("q", Source, layout))
	
	def get_process_fragment(self):
		sigs_d = self.token("d").flatten()
		sigs_q = self.token("q").flatten()
		sync = [If(self.pipe_ce, Cat(*sigs_q).eq(Cat(*sigs_d)))]
		return Fragment(sync=sync)

class Combinator(Actor):
	def __init__(self, layout, *subrecords):
		source = Record(layout)
		subrecords = [source.subrecord(*subr) for subr in subrecords]
		eps = [("sink{0}".format(n), Sink, r)
			for x in enumerate(subrecords)]
		ep_source = ("source", Source, source)
		eps.append(ep_source)
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.COMBINATORIAL),
			*eps)

	def get_fragment(self):
		source = self.endpoints["source"]
		sinks = [self.endpoints["sink{0}".format(n)]
			for n in range(len(self.endpoints)-1)]
		comb = [source.stb.eq(optree('&', [sink.stb for sink in sinks]))]
		comb += [sink.ack.eq(source.ack & source.stb) for sink in sinks]
		return Fragment(comb)

class Splitter(Actor):
	def __init__(self, layout, *subrecords):
		sink = Record(layout)
		subrecords = [sink.subrecord(*subr) for subr in subrecords]
		eps = [("source{0}".format(n), Source, r)
			for n, r in enumerate(subrecords)]
		ep_sink = ("sink", Sink, sink)
		eps.append(ep_sink)
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.COMBINATORIAL),
			*eps)
		
	# TODO def get_fragment(self):
