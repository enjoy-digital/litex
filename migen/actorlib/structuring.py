from migen.fhdl.std import *
from migen.flow.actor import *

def _rawbits_layout(l):
	if isinstance(l, int):
		return [("rawbits", l)]
	else:
		return l

class Cast(CombinatorialActor):
	def __init__(self, layout_from, layout_to, reverse_from=False, reverse_to=False):
		self.sink = Sink(_rawbits_layout(layout_from))
		self.source = Source(_rawbits_layout(layout_to))
		CombinatorialActor.__init__(self)

		###

		sigs_from = self.sink.payload.flatten()
		if reverse_from:
			sigs_from = list(reversed(sigs_from))
		sigs_to = self.source.payload.flatten()
		if reverse_to:
			sigs_to = list(reversed(sigs_to))
		if sum(flen(s) for s in sigs_from) != sum(flen(s) for s in sigs_to):
			raise TypeError
		self.comb += Cat(*sigs_to).eq(Cat(*sigs_from))

def pack_layout(l, n):
	return [("chunk"+str(i), l) for i in range(n)]

class Unpack(Module):
	def __init__(self, n, layout_to, reverse=False):
		self.sink = Sink(pack_layout(layout_to, n))
		self.source = Source(layout_to)
		self.busy = Signal()

		###

		mux = Signal(max=n)
		last = Signal()
		self.comb += [
			last.eq(mux == (n-1)),
			self.source.stb.eq(self.sink.stb),
			self.sink.ack.eq(last & self.source.ack)
		]
		self.sync += [
			If(self.source.stb & self.source.ack,
				If(last,
					mux.eq(0)
				).Else(
					mux.eq(mux + 1)
				)
			)
		]
		cases = {}
		for i in range(n):
			chunk = n-i-1 if reverse else i
			cases[i] = [self.source.payload.raw_bits().eq(getattr(self.sink.payload, "chunk"+str(chunk)).raw_bits())]
		self.comb += Case(mux, cases).makedefault()

class Pack(Module):
	def __init__(self, layout_from, n, reverse=False):
		self.sink = Sink(layout_from)
		self.source = Source(pack_layout(layout_from, n))
		self.busy = Signal()

		###

		demux = Signal(max=n)

		load_part = Signal()
		strobe_all = Signal()
		cases = {}
		for i in range(n):
			chunk = n-i-1 if reverse else i
			cases[i] = [getattr(self.source.payload, "chunk"+str(chunk)).raw_bits().eq(self.sink.payload.raw_bits())]
		self.comb += [
			self.busy.eq(strobe_all),
			self.sink.ack.eq(~strobe_all | self.source.ack),
			self.source.stb.eq(strobe_all),
			load_part.eq(self.sink.stb & self.sink.ack)
		]
		self.sync += [
			If(self.source.ack, strobe_all.eq(0)),
			If(load_part,
				Case(demux, cases),
				If(demux == (n - 1),
					demux.eq(0),
					strobe_all.eq(1)
				).Else(
					demux.eq(demux + 1)
				)
			)
		]
