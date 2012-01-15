from migen.fhdl.structure import *
from migen.fhdl.structure import _make_signal_name
from migen.corelogic.misc import optree
from migen.corelogic.record import *

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
		if isinstance(self, Sink):
			self.stb = Signal(namer="stb_i")
			self.ack = Signal(namer="ack_o")
		else:
			self.stb = Signal(namer="stb_o")
			self.ack = Signal(namer="ack_i")
	
	def token_signal(self):
		sigs = self.token.flatten()
		assert(len(sigs) == 1)
		return sigs[0]
	
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

def _control_fragment_comb(stb_i, ack_o, stb_o, ack_i, busy):
	return Fragment([stb_o.eq(stb_i), ack_o.eq(ack_i), busy.eq(0)])

def _control_fragment_seq(latency, stb_i, ack_o, stb_o, ack_i, busy, trigger):
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
		busy.eq(~ready)
	]
	sync += [
		If(trigger, mask.eq(1)),
		If(stb_o & ack_i, mask.eq(0))
	]

	return Fragment(comb, sync)

def _control_fragment_pipe(latency, stb_i, ack_o, stb_o, ack_i, busy, pipe_ce):
	valid = Signal(BV(latency))
	if latency > 1:
		sync = [If(pipe_ce, valid.eq(Cat(stb_i, valid[:latency-1])))]
	else:
		sync = [If(pipe_ce, valid.eq(stb_i))]
	last_valid = valid[latency-1]
	
	comb = [
		pipe_ce.eq(ack_i | ~last_valid),
		ack_o.eq(pipe_ce),
		stb_o.eq(last_valid),
		busy.eq(optree('|', [valid[i] for i in range(latency)]))
	]
	
	return Fragment(comb, sync)

class Actor:
	def __init__(self, scheduling_model, *endpoint_descriptions, endpoints=None):
		self.scheduling_model = scheduling_model
		if endpoints is None:
			self.endpoints = {}
			for desc in endpoint_descriptions:
				# desc: (name, Sink/Source, token layout or existing record)
				if isinstance(desc[2], Record):
					token = desc[2]
				else:
					token = Record(desc[2], name=_make_signal_name(desc[0], 1))
				ep = desc[1](token)
				self.endpoints[desc[0]] = ep
		else:
			self.endpoints = endpoints
		self.busy = Signal()
		if self.scheduling_model.model == SchedulingModel.SEQUENTIAL:
			self.trigger = Signal()
		elif self.scheduling_model.model == SchedulingModel.PIPELINE:
			self.pipe_ce = Signal()
	
	def token(self, ep):
		return self.endpoints[ep].token
	
	def filter_endpoints(self, cl):
		return [k for k, v in self.endpoints.items() if isinstance(v, cl)]

	def sinks(self):
		return self.filter_endpoints(Sink)

	def sources(self):
		return self.filter_endpoints(Source)

	def get_control_fragment(self):
		def get_single_ep(l):
			if len(l) != 1:
				raise ValueError("Actors with automatic control fragment must have exactly one sink and one source. Consider using plumbing actors.")
			return self.endpoints[l[0]]
		sink = get_single_ep(self.sinks())
		source = get_single_ep(self.sources())
		stb_i = sink.stb
		ack_o = sink.ack
		stb_o = source.stb
		ack_i = source.ack
		if self.scheduling_model.model == SchedulingModel.COMBINATORIAL:
			return _control_fragment_comb(stb_i, ack_o, stb_o, ack_i, self.busy)
		elif self.scheduling_model.model == SchedulingModel.SEQUENTIAL:
			return _control_fragment_seq(self.scheduling_model.latency, stb_i, ack_o, stb_o, ack_i, self.busy, self.trigger)
		elif self.scheduling_model.model == SchedulingModel.PIPELINE:
			return _control_fragment_pipe(self.scheduling_model.latency, stb_i, ack_o, stb_o, ack_i, self.busy, self.pipe_ce)
		elif self.scheduling_model.model == SchedulingModel.DYNAMIC:
			raise NotImplementedError("Actor classes with dynamic scheduling must overload get_control_fragment or get_fragment")
	
	def get_process_fragment(self):
		raise NotImplementedError("Actor classes must overload get_process_fragment")
	
	def get_fragment(self):
		return self.get_control_fragment() + self.get_process_fragment()
	
	def __repr__(self):
		return "<" + self.__class__.__name__ + " " + repr(self.scheduling_model) + " " + repr(self.sinks()) + " " + repr(self.sources()) + ">"

def get_conn_fragment(source, sink):
	assert isinstance(source, Source)
	assert isinstance(sink, Sink)
	assert sink.token.compatible(source.token)
	sigs_source = source.token.flatten()
	sigs_sink = sink.token.flatten()
	comb = [
		source.ack.eq(sink.ack),
		sink.stb.eq(source.stb),
		Cat(*sigs_sink).eq(Cat(*sigs_source))
	]
	return Fragment(comb)
