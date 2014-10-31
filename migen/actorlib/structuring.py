from migen.fhdl.std import *
from migen.genlib.record import *
from migen.flow.actor import *

def _rawbits_layout(l):
	if isinstance(l, int):
		return [("rawbits", l)]
	else:
		return l

class Cast(CombinatorialActor):
	def __init__(self, layout_from, layout_to, reverse_from=False, reverse_to=False, packetized=False):
		self.sink = Sink(_rawbits_layout(layout_from), packetized)
		self.source = Source(_rawbits_layout(layout_to), packetized)
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
	def __init__(self, n, layout_to, reverse=False, packetized=False):
		self.sink = Sink(pack_layout(layout_to, n), packetized)
		self.source = Source(layout_to, packetized)
		self.busy = Signal()

		###

		mux = Signal(max=n)
		first = Signal()
		last = Signal()
		self.comb += [
			first.eq(mux == 0),
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

		if packetized:
			self.comb += [
				self.source.sop.eq(self.source.stb & self.sink.sop & first),
				self.source.eop.eq(self.source.stb & self.sink.eop & last)
			]

class Pack(Module):
	def __init__(self, layout_from, n, reverse=False, packetized=False):
		self.sink = sink = Sink(layout_from, packetized)
		self.source = source = Source(pack_layout(layout_from, n), packetized)
		self.busy = Signal()

		###

		demux = Signal(max=n)

		load_part = Signal()
		strobe_all = Signal()
		cases = {}
		for i in range(n):
			chunk = n-i-1 if reverse else i
			cases[i] = [getattr(source.payload, "chunk"+str(chunk)).raw_bits().eq(sink.payload.raw_bits())]
		self.comb += [
			self.busy.eq(strobe_all),
			sink.ack.eq(~strobe_all | source.ack),
			source.stb.eq(strobe_all),
			load_part.eq(sink.stb & sink.ack)
		]

		if packetized:
			demux_last = ((demux == (n - 1)) | sink.eop)
		else:
			demux_last = (demux == (n - 1))

		self.sync += [
			If(source.ack, strobe_all.eq(0)),
			If(load_part,
				Case(demux, cases),
				If(demux_last,
					demux.eq(0),
					strobe_all.eq(1)
				).Else(
					demux.eq(demux + 1)
				)
			)
		]

		if packetized:
			sop = Signal()
			eop = Signal()
			self.sync += [
				If(source.stb & source.ack,
					sop.eq(load_part & sink.sop)
				).Else(
					sop.eq((load_part & sink.sop) | sop)
				),
				eop.eq(load_part & sink.eop)
			]
			self.comb += [
				source.sop.eq(source.stb & sop),
				source.eop.eq(source.stb & eop),
			]

class Chunkerize(CombinatorialActor):
	def __init__(self, layout_from, layout_to, n, reverse=False, packetized=False):
		self.sink = Sink(layout_from, packetized)
		self.source = Source(pack_layout(layout_to, n), packetized)
		CombinatorialActor.__init__(self)

		###

		for i in range(n):
			chunk = n-i-1 if reverse else i
			for f in layout_from:
				src = getattr(self.sink, f[0])
				dst = getattr(getattr(self.source, "chunk"+str(chunk)), f[0])
				self.comb += dst.eq(src[i*flen(src)//n:(i+1)*flen(src)//n])

class Unchunkerize(CombinatorialActor):
	def __init__(self, layout_from, n, layout_to, reverse=False, packetized=False):
		self.sink = Sink(pack_layout(layout_from, n), packetized)
		self.source = Source(layout_to, packetized)
		CombinatorialActor.__init__(self)

		###

		for i in range(n):
			chunk = n-i-1 if reverse else i
			for f in layout_from:
				src = getattr(getattr(self.sink, "chunk"+str(chunk)), f[0])
				dst = getattr(self.source, f[0])
				self.comb += dst[i*flen(dst)//n:(i+1)*flen(dst)//n].eq(src)

class Converter(Module):
	def __init__(self, layout_from, layout_to, packetized=False, reverse=False):
		self.sink = Sink(layout_from, packetized)
		self.source = Source(layout_to, packetized)
		self.busy = Signal()

		###

		width_from = flen(self.sink.payload.raw_bits())
		width_to = flen(self.source.payload.raw_bits())

		# downconverter
		if width_from > width_to:
			if width_from % width_to:
				raise ValueError
			ratio = width_from//width_to
			self.submodules.chunkerize = Chunkerize(layout_from, layout_to, ratio, reverse, packetized)
			self.submodules.unpack = Unpack(ratio, layout_to, packetized=packetized)

			self.comb += [
				Record.connect(self.sink, self.chunkerize.sink),
				Record.connect(self.chunkerize.source, self.unpack.sink),
				Record.connect(self.unpack.source, self.source),
				self.busy.eq(self.unpack.busy)
			]
		# upconverter
		elif width_to > width_from:
			if width_to % width_from:
				raise ValueError
			ratio = width_to//width_from
			self.submodules.pack = Pack(layout_from, ratio, packetized=packetized)
			self.submodules.unchunkerize = Unchunkerize(layout_from, ratio, layout_to, reverse, packetized)

			self.comb += [
				Record.connect(self.sink, self.pack.sink),
				Record.connect(self.pack.source, self.unchunkerize.sink),
				Record.connect(self.unchunkerize.source, self.source),
				self.busy.eq(self.pack.busy)
			]
		# direct connection
		else:
			self.comb += Record.connect(self.sink, self.source)

class Pipeline(Module):
	def __init__(self, *modules):
		n = len(modules)
		m = modules[0]
		# expose sink of first module
		# if available
		if hasattr(m, "sink"):
			self.sink = m.sink
		# use of busy is encouraged
		# but not mandatory
		if hasattr(m, "busy"):
			busy = m.busy
		else:
			busy = 0
		for i in range(1, n):
			m_n = modules[i]
			if hasattr(m_n, "busy"):
				busy_n = m_n.busy
			else:
				busy_n = 0
			self.comb += m.source.connect(m_n.sink)
			m = m_n
			busy = busy | busy_n
		# expose source of last module
		# if available
		if hasattr(m, "source"):
			self.source = m.source
		self.busy = busy
