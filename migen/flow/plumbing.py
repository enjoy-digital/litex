from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.corelogic.record import *
from migen.corelogic.misc import optree

class Buffer(Actor):
	def __init__(self, layout):
		self.d = Record(layout)
		self.q = Record(layout)
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.PIPELINE, 1),
			self.d, self.q)
	
	def get_process_fragment(self):
		sigs_d = self.d.flatten()
		sigs_q = self.q.flatten()
		sync = [If(self.pipe_ce, Cat(*sigs_q).eq(Cat(*sigs_d)))]
		return Fragment(sync=sync)

class Combinator(Actor):
	def __init__(self, layout, *subrecords):
		self.destination = Record(layout)
		self.ins = [self.destination.subrecord(*subr) for subr in subrecords]
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.COMBINATORIAL),
			self.ins, self.destination)

	def get_process_fragment(self):
		return Fragment() # nothing to do
	
	def get_control_fragment(self):
		source = self.sources()[0]
		sinks = self.sinks()
		comb = [source.stb.eq(optree('&', [sink.stb for sink in sinks]))]
		comb += [sink.ack.eq(source.ack & source.stb) for sink in sinks]
		return Fragment(comb)

class Splitter(Actor):
	def __init__(self, layout, *subrecords):
		self.source = Record(layout)
		self.outs = [self.source.subrecord(*subr) for subr in subrecords]
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.COMBINATORIAL),
			self.source, self.outs)
		
	def get_process_fragment(self):
		return Fragment() # nothing to do
	
	# TODO def get_control_fragment(self):
