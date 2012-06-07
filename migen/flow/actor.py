from migen.fhdl.structure import *
from migen.corelogic.misc import optree
from migen.corelogic.record import *

class Endpoint:
	def __init__(self, token):
		self.token = token
		if isinstance(self, Sink):
			self.stb = Signal(name="stb_i")
			self.ack = Signal(name="ack_o")
		else:
			self.stb = Signal(name="stb_o")
			self.ack = Signal(name="ack_i")
	
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

class Actor:
	def __init__(self, *endpoint_descriptions, endpoints=None):
		if endpoints is None:
			self.endpoints = {}
			for desc in endpoint_descriptions:
				# desc: (name, Sink/Source, token layout or existing record)
				if isinstance(desc[2], Record):
					token = desc[2]
				else:
					token = Record(desc[2])
				ep = desc[1](token)
				self.endpoints[desc[0]] = ep
		else:
			self.endpoints = endpoints
		self.busy = Signal()

	def token(self, ep):
		return self.endpoints[ep].token
	
	def filter_endpoints(self, cl):
		return [k for k, v in self.endpoints.items() if isinstance(v, cl)]

	def sinks(self):
		return self.filter_endpoints(Sink)

	def sources(self):
		return self.filter_endpoints(Source)

	def get_control_fragment(self):
		raise NotImplementedError("Actor classes must overload get_control_fragment or get_fragment")

	def get_process_fragment(self):
		raise NotImplementedError("Actor classes must overload get_process_fragment or get_fragment")
	
	def get_fragment(self):
		return self.get_control_fragment() + self.get_process_fragment()
	
	def __repr__(self):
		return "<" + self.__class__.__name__ + " " + repr(self.scheduling_model) + " " + repr(self.sinks()) + " " + repr(self.sources()) + ">"

class BinaryActor(Actor):
	def get_binary_control_fragment(self, stb_i, ack_o, stb_o, ack_i):
		raise NotImplementedError("Binary actor classes must overload get_binary_control_fragment")

	def get_control_fragment(self):
		def get_single_ep(l):
			if len(l) != 1:
				raise ValueError("Binary actors have exactly one sink and one source. Consider using plumbing actors.")
			return self.endpoints[l[0]]
		sink = get_single_ep(self.sinks())
		source = get_single_ep(self.sources())
		return self.get_binary_control_fragment(sink.stb, sink.ack, source.stb, source.ack)

class CombinatorialActor(BinaryActor):
	def get_binary_control_fragment(self, stb_i, ack_o, stb_o, ack_i):
		return Fragment([stb_o.eq(stb_i), ack_o.eq(ack_i), self.busy.eq(0)])

class SequentialActor(BinaryActor):
	def __init__(self, delay, *endpoint_descriptions, endpoints=None):
		self.delay = delay
		self.trigger = Signal()
		BinaryActor.__init__(*endpoint_descriptions, endpoints=endpoints)

	def get_binary_control_fragment(self, stb_i, ack_o, stb_o, ack_i):
		ready = Signal()
		timer = Signal(BV(bits_for(self.delay)))
		comb = [ready.eq(timer == 0)]
		sync = [
			If(self.trigger,
				timer.eq(self.delay)
			).Elif(~ready,
				timer.eq(timer - 1)
			)
		]
		
		mask = Signal()
		comb += [
			stb_o.eq(ready & mask),
			self.trigger.eq(stb_i & (ack_i | ~mask) & ready),
			ack_o.eq(self.trigger),
			busy.eq(~ready)
		]
		sync += [
			If(self.trigger, mask.eq(1)),
			If(stb_o & ack_i, mask.eq(0))
		]

		return Fragment(comb, sync)

class PipelinedActor(BinaryActor):
	def __init__(self, latency, *endpoint_descriptions, endpoints=None):
		self.latency = latency
		self.pipe_ce = Signal()
		BinaryActor.__init__(*endpoint_descriptions, endpoints=endpoints)

	def get_binary_control_fragment(self, stb_i, ack_o, stb_o, ack_i):
		valid = Signal(BV(self.latency))
		if self.latency > 1:
			sync = [If(self.pipe_ce, valid.eq(Cat(stb_i, valid[:self.latency-1])))]
		else:
			sync = [If(self.pipe_ce, valid.eq(stb_i))]
		last_valid = valid[self.latency-1]
		
		comb = [
			self.pipe_ce.eq(ack_i | ~last_valid),
			ack_o.eq(self.pipe_ce),
			stb_o.eq(last_valid),
			busy.eq(optree("|", [valid[i] for i in range(self.latency)]))
		]
		
		return Fragment(comb, sync)
		
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
