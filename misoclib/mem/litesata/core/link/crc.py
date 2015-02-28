from collections import OrderedDict
from misoclib.mem.litesata.common import *

class CRCEngine(Module):
	"""Cyclic Redundancy Check Engine

	Compute next CRC value from last CRC value and data input using
	an optimized asynchronous LFSR.

	Parameters
	----------
	width : int
		Width of the data bus and CRC.
	polynom : int
		Polynom of the CRC (ex: 0x04C11DB7 for IEEE 802.3 CRC)

	Attributes
	----------
	d : in
		Data input.
	last : in
		last CRC value.
	next :
		next CRC value.
	"""
	def __init__(self, width, polynom):
		self.d = Signal(width)
		self.last = Signal(width)
		self.next = Signal(width)

		###

		def _optimize_eq(l):
			"""
			Replace even numbers of XORs in the equation
			with an equivalent XOR
			"""
			d = OrderedDict()
			for e in l:
				if e in d:
					d[e] += 1
				else:
					d[e] = 1
			r = []
			for key, value in d.items():
				if value%2 != 0:
					r.append(key)
			return r

		new = Signal(32)
		self.comb += new.eq(self.last ^ self.d)

		# compute and optimize CRC's LFSR
		curval = [[("new", i)] for i in range(width)]
		for i in range(width):
			feedback = curval.pop()
			for j in range(width-1):
				if (polynom & (1<<(j+1))):
					curval[j] += feedback
				curval[j] = _optimize_eq(curval[j])
			curval.insert(0, feedback)

		# implement logic
		for i in range(width):
			xors = []
			for t, n in curval[i]:
				if t == "new":
					xors += [new[n]]
			self.comb += self.next[i].eq(optree("^", xors))

@DecorateModule(InsertReset)
@DecorateModule(InsertCE)
class LiteSATACRC(Module):
	"""SATA CRC

	Implement a SATA CRC generator/checker

	Attributes
	----------
	value : out
		CRC value (used for generator).
	error : out
		CRC error (used for checker).
	"""
	width = 32
	polynom = 0x04C11DB7
	init = 0x52325032
	check = 0x00000000
	def __init__(self, dw=32):
		self.d = Signal(self.width)
		self.value = Signal(self.width)
		self.error = Signal()

		###

		engine = CRCEngine(self.width, self.polynom)
		self.submodules += engine
		reg_i = Signal(self.width, reset=self.init)
		self.sync += reg_i.eq(engine.next)
		self.comb += [
			engine.d.eq(self.d),
			engine.last.eq(reg_i),

			self.value.eq(reg_i),
			self.error.eq(engine.next != self.check)
		]


class CRCInserter(Module):
	"""CRC Inserter

	Append a CRC at the end of each packet.

	Parameters
	----------
	layout : layout
		Layout of the dataflow.

	Attributes
	----------
	sink : in
		Packets input without CRC.
	source : out
		Packets output with CRC.
	"""
	def __init__(self, crc_class, layout):
		self.sink = sink = Sink(layout)
		self.source = source = Source(layout)
		self.busy = Signal()

		###

		dw = flen(sink.d)
		crc = crc_class(dw)
		fsm = FSM(reset_state="IDLE")
		self.submodules += crc, fsm

		fsm.act("IDLE",
			crc.reset.eq(1),
			sink.ack.eq(1),
			If(sink.stb & sink.sop,
				sink.ack.eq(0),
				NextState("COPY"),
			)
		)
		fsm.act("COPY",
			crc.ce.eq(sink.stb & source.ack),
			crc.d.eq(sink.d),
			Record.connect(sink, source),
			source.eop.eq(0),
			If(sink.stb & sink.eop & source.ack,
				NextState("INSERT"),
			)
		)
		ratio = crc.width//dw
		if ratio > 1:
			cnt = Signal(max=ratio, reset=ratio-1)
			cnt_done = Signal()
			fsm.act("INSERT",
				source.stb.eq(1),
				chooser(crc.value, cnt, source.d, reverse=True),
				If(cnt_done,
					source.eop.eq(1),
					If(source.ack, NextState("IDLE"))
				)
			)
			self.comb += cnt_done.eq(cnt == 0)
			self.sync += \
				If(fsm.ongoing("IDLE"),
					cnt.eq(cnt.reset)
				).Elif(fsm.ongoing("INSERT") & ~cnt_done,
					cnt.eq(cnt - source.ack)
				)
		else:
			fsm.act("INSERT",
				source.stb.eq(1),
				source.eop.eq(1),
				source.d.eq(crc.value),
				If(source.ack, NextState("IDLE"))
			)
		self.comb += self.busy.eq(~fsm.ongoing("IDLE"))

class CRCChecker(Module):
	"""CRC Checker

	Check CRC at the end of each packet.

	Parameters
	----------
	layout : layout
		Layout of the dataflow.

	Attributes
	----------
	sink : in
		Packets input with CRC.
	source : out
		Packets output without CRC and "error" set to 0
		on eop when CRC OK / set to 1 when CRC KO.
	"""
	def __init__(self, crc_class, layout):
		self.sink = sink = Sink(layout)
		self.source = source = Source(layout)
		self.busy = Signal()

		###

		dw = flen(sink.d)
		crc = crc_class(dw)
		self.submodules += crc
		ratio = crc.width//dw

		error = Signal()
		fifo = InsertReset(SyncFIFO(layout, ratio + 1))
		self.submodules += fifo

		fsm = FSM(reset_state="RESET")
		self.submodules += fsm

		fifo_in = Signal()
		fifo_out = Signal()
		fifo_full = Signal()

		self.comb += [
			fifo_full.eq(fifo.fifo.level == ratio),
			fifo_in.eq(sink.stb & (~fifo_full | fifo_out)),
			fifo_out.eq(source.stb & source.ack),

			Record.connect(sink, fifo.sink),
			fifo.sink.stb.eq(fifo_in),
			self.sink.ack.eq(fifo_in),

			source.stb.eq(sink.stb & fifo_full),
			source.sop.eq(fifo.source.sop),
			source.eop.eq(sink.eop),
			fifo.source.ack.eq(fifo_out),
			source.payload.eq(fifo.source.payload),

			source.error.eq(sink.error | crc.error),
		]

		fsm.act("RESET",
			crc.reset.eq(1),
			fifo.reset.eq(1),
			NextState("IDLE"),
		)
		fsm.act("IDLE",
			crc.d.eq(sink.d),
			If(sink.stb & sink.sop & sink.ack,
				crc.ce.eq(1),
				NextState("COPY")
			)
		)
		fsm.act("COPY",
			crc.d.eq(sink.d),
			If(sink.stb & sink.ack,
				crc.ce.eq(1),
				If(sink.eop,
					NextState("RESET")
				)
			)
		)
		self.comb += self.busy.eq(~fsm.ongoing("IDLE"))

class LiteSATACRCInserter(CRCInserter):
	def __init__(self, description):
		CRCInserter.__init__(self, LiteSATACRC, description)

class LiteSATACRCChecker(CRCChecker):
	def __init__(self, description):
		CRCChecker.__init__(self, LiteSATACRC, description)
