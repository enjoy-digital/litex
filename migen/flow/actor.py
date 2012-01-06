from migen.fhdl.structure import *

class SchedulingModel:
	COMBINATORIAL, SEQUENTIAL, PIPELINE, DYNAMIC = range(4)
	
	def __init__(self, model, latency=1):
		self.model = model
		self.latency = latency
	
	def __repr__(self):
		if self.model == SchedulingModel.COMBINATORIAL:
			return "<SchedulingModel: COMBINATORIAL>"
		elif self.model == SchedulingModel.SEQUENTIAL:
			return "<SchedulingModel: SEQUENTIAL({0})>".format(self.latency)
		elif self.model == SchedulingModel.PIPELINE:
			return "<SchedulingModel: PIPELINE({0})>".format(self.latency)
		elif self.model == SchedulingModel.DYNAMIC:
			return "<SchedulingModel: DYNAMIC>"
		else:
			raise AttributeError

class Endpoint:
	def __init__(self, token):
		self.token = token
		self.stb = Signal()
		self.ack = Signal()
	
	def __hash__(self):
		return id(self)
		
	def __repr__(self):
		return "<Endpoint " + str(self.token) + ">"


class Sink(Endpoint):
	def __repr__(self):
		return "<Sink " + str(self.token) + ">"

class Source(Endpoint):
	def __repr__(self):
		return "<Source " + str(self.token) + ">"

def _control_fragment_comb(stb_i, ack_o, stb_o, ack_i):
	return Fragment([stb_o.eq(stb_i), ack_o.eq(ack_i)])

def _control_fragment_seq(latency, stb_i, ack_o, stb_o, ack_i, trigger):
	ready = Signal()
	timer = Signal(BV(bits_for(latency)))
	comb = [ready.eq(timer == 0)]
	sync = [
		If(trigger,
			timer.eq(latency)
		).Elif(~ready,
			timer.eq(timer - 1)
		)
	]
	
	mask = Signal()
	comb += [
		stb_o.eq(ready & mask),
		trigger.eq(stb_i & (ack_i | ~mask) & ready),
		ack_o.eq(trigger),
	]
	sync += [
		If(trigger, mask.eq(1)),
		If(stb_o & ack_i, mask.eq(0))
	]

	return Fragment(comb, sync)

def _control_fragment_pipe(latency, stb_i, ack_o, stb_o, ack_i, pipe_ce):
	valid = Signal(BV(latency))
	if latency > 1:
		sync = [If(pipe_ce, valid.eq(Cat(stb_i, valid[:latency-1])))]
	else:
		sync = [If(pipe_ce, valid.eq(stb_i))]
	last_valid = valid[latency-1]
	
	comb = [
		pipe_ce.eq(ack_i | ~last_valid),
		ack_o.eq(pipe_ce),
		stb_o.eq(last_valid)
	]
	
	return Fragment(comb, sync)

class Actor:
	def __init__(self, scheduling_model, sinks=None, sources=None, endpoints=None):
		self.scheduling_model = scheduling_model
		if endpoints is None:
			if isinstance(sinks, list):
				self.endpoints = [Sink(sink) for sink in sinks]
			else:
				self.endpoints = [Sink(sinks)]
			if isinstance(sources, list):
				self.endpoints += [Source(source) for source in sources]
			else:
				self.endpoints.append(Source(sources))
		else:
			self.endpoints = endpoints
		if self.scheduling_model.model == SchedulingModel.SEQUENTIAL:
			self.trigger = Signal()
		elif self.scheduling_model.model == SchedulingModel.PIPELINE:
			self.pipe_ce = Signal()
	
	def sinks(self):
		return [x for x in self.endpoints if isinstance(x, Sink)]

	def sources(self):
		return [x for x in self.endpoints if isinstance(x, Source)]
		
	def get_control_fragment(self):
		if len(self.endpoints) != 2:
			raise ValueError("Actors with automatic control fragment must have exactly two endpoints.")
		if isinstance(self.endpoints[0], Sink):
			assert(isinstance(self.endpoints[1], Source))
			sink = self.endpoints[0]
			source = self.endpoints[1]
		elif isinstance(self.endpoints[0], Source):
			assert(isinstance(self.endpoints[1], Sink))
			sink = self.endpoints[1]
			source = self.endpoints[0]
		else:
			raise ValueError("Actors with automatic control fragment must have one sink and one source. Consider using plumbing actors.")
		stb_i = sink.stb
		ack_o = sink.ack
		stb_o = source.stb
		ack_i = source.ack
		if self.scheduling_model.model == SchedulingModel.COMBINATORIAL:
			return _control_fragment_comb(stb_i, ack_o, stb_o, ack_i)
		elif self.scheduling_model.model == SchedulingModel.SEQUENTIAL:
			return _control_fragment_seq(self.scheduling_model.latency, stb_i, ack_o, stb_o, ack_i, self.trigger)
		elif self.scheduling_model.model == SchedulingModel.PIPELINE:
			return _control_fragment_pipe(self.scheduling_model.latency, stb_i, ack_o, stb_o, ack_i, self.pipe_ce)
		elif self.scheduling_model.model == SchedulingModel.DYNAMIC:
			raise NotImplementedError("Actor classes with dynamic scheduling must overload get_control_fragment")
	
	def get_process_fragment(self):
		raise NotImplementedError("Actor classes must overload get_process_fragment")
	
	def __repr__(self):
		return "<Actor " + repr(self.scheduling_model) + " " + repr(self.sinks()) + " " + repr(self.sources()) + ">"

def get_conn_control_fragment(source, sink):
	assert(isinstance(source, Source))
	assert(isinstance(sink, Sink))
	comb = [
		source.ack.eq(sink.ack),
		sink.stb.eq(source.stb)
	]
	return Fragment(comb)
	
def get_conn_process_fragment(source, sink):
	assert(isinstance(source, Source))
	assert(isinstance(sink, Sink))
	assert(sink.token.compatible(source.token))
	sigs_source = source.token.flatten()
	sigs_sink = sink.token.flatten()
	comb = [Cat(*sigs_sink).eq(Cat(*sigs_source))]
	return Fragment(comb)
