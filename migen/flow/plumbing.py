from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.corelogic.record import *
from migen.corelogic.misc import optree

class Buffer(Actor):
	def __init__(self, template):
		self.d = Record(template)
		self.q = Record(template)
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.PIPELINE, 1),
			self.d, self.q)
	
	def get_process_fragment(self):
		sigs_d = self.d.flatten()
		sigs_q = self.q.flatten()
		sync = [Cat(*sigs_q).eq(Cat(*sigs_d))]
		return Fragment(sync=sync)

class Combinator(Actor):
	def __init__(self, destination, *subrecords):
		self.ins = [destination.subrecord(*subr) for subr in subrecords]
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.COMBINATORIAL),
			self.ins, destination)

	def get_process_fragment(self):
		return Fragment() # nothing to do
	
	def get_control_fragment(self):
		comb = [self.sources[0].stb.eq(optree('&', [sink.stb for sink in self.sinks]))]
		comb += [sink.ack.eq(self.sources[0].ack & self.sources[0].stb) for sink in self.sinks]
		return Fragment(comb)

class Splitter(Actor):
	def __init__(self, source, *subrecords):
		self.outs = [source.subrecord(*subr) for subr in subrecords]
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.COMBINATORIAL),
			source, self.outs)
		
	def get_process_fragment(self):
		return Fragment() # nothing to do
	
	# TODO def get_control_fragment(self):
