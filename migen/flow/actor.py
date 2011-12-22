from migen.fhdl.structure import *
from migen.corelogic.optree import optree

class SchedulingModel:
	COMBINATORIAL, SEQUENTIAL, PIPELINE, DYNAMIC = range(6)
	
	def __init__(self, model, latency=1):
		self.model = model
		self.latency = latency
	
	def __str__(self):
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

class Sink:
	def __init__(self, actor, token):
		self.actor = actor
		self.token = token
		self.stb_i = Signal()
		self.ack_o = Signal()

class Source:
	def __init__(self, actor, token):
		self.actor = actor
		self.token = token
		self.stb_o = Signal()
		self.ack_i = Signal()

def _control_fragment_comb(l_stb_i, l_ack_o, l_stb_o, l_ack_i):
	en = Signal()
	comb = [en.eq(optree('&', l_stb_i + l_ack_i))]
	comb += [o.eq(en) for o in l_ack_o + l_stb_o]
	return Fragment(comb)

def _control_fragment_seq(latency, l_stb_i, l_ack_o, l_stb_o, l_ack_i, trigger):
	ready = Signal()
	timer = Signal(BV(bits_for(latency)))
	comb = [ready.eq(timer == 0))]
	sync = [
		If(trigger,
			timer.eq(latency)
		).Elif(~ready,
			timer.eq(timer - 1)
		)
	]
	
	nsources = len(l_stb_o)
	mask = Signal(BV(nsources))
	sync.append(If(trigger, mask.eq(0)).Else(mask.eq(mask | Cat(*l_ack_i))))

	comb.append(Cat(*l_stb_o).eq(Replicate(len(l_stb_o), ready) & ~mask))
	comb.append(Cat(*l_ack_o).eq(Replicate(len(l_ack_o), trigger)))
	
	stb_all = Signal()
	comb.append(stb_all.eq(optree('&', l_stb_i)))
	comb.append(trigger.eq(ready & stb_all & ((mask | Cat(*l_ack_i)) == Replicate(nsources, 1))))

	return Fragment(comb, sync)

def _control_fragment_pipe(latency, l_stb_i, l_ack_o, l_stb_o, l_ack_i, pipe_ce):
	stb_all = Signal()
	comb = [stb_all.eq(optree('&', l_stb_i))]
	valid = Signal(BV(latency))
	if latency > 1:
		sync = [If(pipe_ce, valid.eq(Cat(stb_all, valid[1:])))]
	else:
		sync = [If(pipe_ce, valid.eq(stb_all))]
	last_valid = valid[latency-1]
	
	nsources = len(l_stb_o)
	mask = Signal(BV(nsources))
	sync.append(If(pipe_ce, mask.eq(0)).Else(mask.eq(mask | Cat(*l_ack_i))))
	
	comb.append(Cat(*l_stb_o).eq(Replicate(len(l_stb_o), last_valid) & ~mask))
	comb.append(Cat(*l_ack_o).eq(Replicate(len(l_ack_o), pipe_ce)))
	
	comb.append(pipe_ce.eq(~last_valid | ((mask | Cat(*l_ack_i)) == Replicate(nsources, 1))))
	
	return Fragment(comb, sync)

class Actor:
	def __init__(self, scheduling_model, sinks, sources):
		self.scheduling_model = scheduling_model
		self.sinks = sinks
		self.sources = sources
		if self.scheduling_model.model == SEQUENTIAL:
			self.trigger = Signal()
		elif self.scheduling_model.model == PIPELINE:
			self.pipe_ce = Signal()
	
	def get_control_fragment():
		l_stb_i = [e.stb_i for e in self.sinks]
		l_ack_o = [e.ack_o for e in self.sinks]
		l_stb_o = [e.stb_o for e in self.sources]
		l_ack_i = [e.ack_i for e in self.sources]
		if self.scheduling_model.model == COMBINATORIAL:
			return _control_fragment_comb(l_stb_i, l_ack_o, l_stb_o, l_ack_i)
		elif self.scheduling_model.model == SEQUENTIAL:
			return _control_fragment_seq(self.scheduling_model.latency, l_stb_i, l_ack_o, l_stb_o, l_ack_i, self.trigger)
		elif self.scheduling_model.model == PIPELINE:
			return _control_fragment_pipe(self.scheduling_model.latency, l_stb_i, l_ack_o, l_stb_o, l_ack_i, self.pipe_ce)
		elif self.scheduling_model.model == DYNAMIC:
			raise NotImplementedError("Actor classes with dynamic scheduling must overload get_control_fragment")
	
	def get_process_fragment():
		raise NotImplementedError("Actor classes must overload get_process_fragment")
