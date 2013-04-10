from migen.fhdl.structure import *
from migen.fhdl.module import Module
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

class _Endpoint(Record):
	def __init__(self, layout):
		full_layout = [
			("payload", _make_m2s(layout)),
			("stb", 1, DIR_M_TO_S),
			("ack", 1, DIR_S_TO_M)
		]
		Record.__init__(self, full_layout)

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
	for k, v in obj.__dict__.items():
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
		self.build_binary_control(sink.stb, sink.ack, source.stb, source.ack, *args, **kwargs)

	def build_binary_control(self, stb_i, ack_o, stb_o, ack_i):
		raise NotImplementedError("Binary actor classes must overload build_binary_control_fragment")

class CombinatorialActor(BinaryActor):
	def build_binary_control(self, stb_i, ack_o, stb_o, ack_i):
		self.comb += [stb_o.eq(stb_i), ack_o.eq(ack_i), self.busy.eq(0)]

class SequentialActor(BinaryActor):
	def __init__(self, delay):
		self.trigger = Signal()
		BinaryActor.__init__(self, delay)

	def build_binary_control(self, stb_i, ack_o, stb_o, ack_i, delay):
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
			stb_o.eq(ready & mask),
			self.trigger.eq(stb_i & (ack_i | ~mask) & ready),
			ack_o.eq(self.trigger),
			self.busy.eq(~ready)
		]
		self.sync += [
			If(self.trigger, mask.eq(1)),
			If(stb_o & ack_i, mask.eq(0))
		]

class PipelinedActor(BinaryActor):
	def __init__(self, latency):
		self.pipe_ce = Signal()
		BinaryActor.__init__(self, latency)

	def build_binary_control(self, stb_i, ack_o, stb_o, ack_i, latency):
		valid = Signal(latency)
		if latency > 1:
			self.sync += If(self.pipe_ce, valid.eq(Cat(stb_i, valid[:latency-1])))
		else:
			self.sync += If(self.pipe_ce, valid.eq(stb_i))
		last_valid = valid[latency-1]
		self.comb += [
			self.pipe_ce.eq(ack_i | ~last_valid),
			ack_o.eq(self.pipe_ce),
			stb_o.eq(last_valid),
			self.busy.eq(optree("|", [valid[i] for i in range(latency)]))
		]
