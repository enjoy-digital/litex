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
	def __init__(self, actor, token):
		self.actor = actor
		self.token = token
		self.stb = Signal()
		self.ack = Signal()

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
	def __init__(self, scheduling_model, sinks, sources):
		self.scheduling_model = scheduling_model
		if isinstance(sinks, list):
			self.sinks = [Endpoint(self, sink) for sink in sinks]
		else:
			self.sinks = [Endpoint(self, sinks)]
		if isinstance(sources, list):
			self.sources = [Endpoint(self, source) for source in sources]
		else:
			self.sources = [Endpoint(self, sources)]
		if self.scheduling_model.model == SchedulingModel.SEQUENTIAL:
			self.trigger = Signal()
		elif self.scheduling_model.model == SchedulingModel.PIPELINE:
			self.pipe_ce = Signal()
	
	def get_control_fragment(self):
		if len(self.sinks) != 1 or len(self.sources) != 1:
			raise ValueError("Actors with automatic control fragment must have one sink and one source. Consider using plumbing actors.")
		stb_i = self.sinks[0].stb
		ack_o = self.sinks[0].ack
		stb_o = self.sources[0].stb
		ack_i = self.sources[0].ack
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
