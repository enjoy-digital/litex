from migen.util.misc import xdir
from migen.fhdl.std import *
from migen.genlib.misc import optree
from migen.genlib.record import *

def _make_m2s(layout):
	r = []
	for f in layout:
		if isinstance(f[1], (int, tuple)):
			r.append((f[0], f[1], DIR_M_TO_S))
		else:
			r.append((f[0], _make_m2s(f[1])))
	return r

class EndpointDescription:
	def __init__(self, payload_layout, param_layout=[], packetized=False):
		self.payload_layout = payload_layout
		self.param_layout = param_layout
		self.packetized = packetized

	def get_full_layout(self):
		reserved = {"stb", "ack", "payload", "param", "sop", "eop", "description"}
		attributed = set()
		for f in self.payload_layout + self.param_layout:
			if f[0] in attributed:
				raise ValueError(f[0] + " already attributed in payload or param layout")
			if f[0] in reserved:
				raise ValueError(f[0] + " cannot be used in endpoint layout")
			attributed.add(f[0])

		full_layout = [
			("payload", _make_m2s(self.payload_layout)),
			("param", _make_m2s(self.param_layout)),
			("stb", 1, DIR_M_TO_S),
			("ack", 1, DIR_S_TO_M)
		]
		if self.packetized:
			full_layout += [
				("sop", 1, DIR_M_TO_S),
				("eop", 1, DIR_M_TO_S)
			]
		return full_layout


class _Endpoint(Record):
	def __init__(self, description_or_layout):
		if isinstance(description_or_layout, EndpointDescription):
			self.description = description_or_layout
		else:
			self.description = EndpointDescription(description_or_layout)
		Record.__init__(self, self.description.get_full_layout())

	def __getattr__(self, name):
		try:
			return getattr(object.__getattribute__(self, "payload"), name)
		except:
			return getattr(object.__getattribute__(self, "param"), name)

class Source(_Endpoint):
	def connect(self, sink):
		return Record.connect(self, sink)

class Sink(_Endpoint):
	def connect(self, source):
		return source.connect(self)

def get_endpoints(obj, filt=_Endpoint):
	if hasattr(obj, "get_endpoints") and callable(obj.get_endpoints):
		return obj.get_endpoints(filt)
	r = dict()
	for k, v in xdir(obj, True):
		if isinstance(v, filt):
			r[k] = v
	return r

def get_single_ep(obj, filt):
	eps = get_endpoints(obj, filt)
	if len(eps) != 1:
		raise ValueError("More than one endpoint")
	return list(eps.items())[0]

class BinaryActor(Module):
	def __init__(self, *args, **kwargs):
		self.busy = Signal()
		sink = get_single_ep(self, Sink)[1]
		source = get_single_ep(self, Source)[1]
		self.build_binary_control(sink, source, *args, **kwargs)

	def build_binary_control(self, sink, source):
		raise NotImplementedError("Binary actor classes must overload build_binary_control_fragment")

class CombinatorialActor(BinaryActor):
	def build_binary_control(self, sink, source):
		self.comb += [
			source.stb.eq(sink.stb),
			sink.ack.eq(source.ack),
			self.busy.eq(0)
		]
		if sink.description.packetized:
			self.comb += [
				source.sop.eq(sink.sop),
				source.eop.eq(sink.eop)
			]

class SequentialActor(BinaryActor):
	def __init__(self, delay):
		self.trigger = Signal()
		BinaryActor.__init__(self, delay)

	def build_binary_control(self, sink, source, delay):
		ready = Signal()
		timer = Signal(max=delay+1)
		self.comb += ready.eq(timer == 0)
		self.sync += If(self.trigger,
				timer.eq(delay)
			).Elif(~ready,
				timer.eq(timer - 1)
			)

		mask = Signal()
		self.comb += [
			source.stb.eq(ready & mask),
			self.trigger.eq(sink.stb & (source.ack | ~mask) & ready),
			sink.ack.eq(self.trigger),
			self.busy.eq(~ready)
		]
		self.sync += [
			If(self.trigger, mask.eq(1)),
			If(source.stb & source.ack, mask.eq(0))
		]
		if sink.packetized:
			self.comb += [
				source.sop.eq(sink.sop),
				source.eop.eq(sink.eop)
			]

class PipelinedActor(BinaryActor):
	def __init__(self, latency):
		self.pipe_ce = Signal()
		BinaryActor.__init__(self, latency)

	def build_binary_control(self, sink, source, latency):
		busy = 0
		valid = sink.stb
		for i in range(latency):
			valid_n = Signal()
			self.sync += If(self.pipe_ce, valid_n.eq(valid))
			valid = valid_n
			busy = busy | valid

		self.comb += [
			self.pipe_ce.eq(source.ack | ~valid),
			sink.ack.eq(self.pipe_ce),
			source.stb.eq(valid),
			self.busy.eq(busy)
		]
		if sink.description.packetized:
			sop = sink.sop
			eop = sink.eop
			for i in range(latency):
				sop_n = Signal()
				eop_n = Signal()
				self.sync += \
					If(self.pipe_ce,
						sop_n.eq(sop),
						eop_n.eq(eop)
					)
				sop = sop_n
				eop = eop_n

			self.comb += [
				source.eop.eq(eop),
				source.sop.eq(sop)
			]
