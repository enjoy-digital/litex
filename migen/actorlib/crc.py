from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState
from migen.genlib.record import *
from migen.genlib.misc import chooser
from migen.genlib.crc import *
from migen.flow.actor import Sink, Source

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
		self.submodules.crc = crc_class(dw)
		self.submodules.fsm = fsm = FSM(reset_state="IDLE")

		fsm.act("IDLE",
			self.crc.reset.eq(1),
			sink.ack.eq(1),
			If(sink.stb & sink.sop,
				sink.ack.eq(0),
				NextState("COPY"),
			)
		)
		fsm.act("COPY",
			self.crc.ce.eq(sink.stb & source.ack),
			self.crc.d.eq(sink.d),
			Record.connect(sink, source),
			source.eop.eq(0),
			If(sink.stb & sink.eop & source.ack,
				NextState("INSERT"),
			)
		)
		ratio = self.crc.width//dw
		cnt = Signal(max=ratio, reset=ratio-1)
		cnt_done = Signal()
		fsm.act("INSERT",
			source.stb.eq(1),
			chooser(self.crc.value, cnt, source.d, reverse=True),
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
		self.comb += self.busy.eq(~fsm.ongoing("IDLE"))

class CRC32Inserter(CRCInserter):
	def __init__(self, layout):
		CRCInserter.__init__(self, CRC32, layout)

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
		Packets output with CRC and "error" set to 0
		on eop when CRC OK / set to 1 when CRC KO.
	"""
	def __init__(self, crc_class, layout):
		self.sink = sink = Sink(layout)
		self.source = source = Source(layout)
		self.busy = Signal()

		###

		dw = flen(sink.d)
		self.submodules.crc = crc_class(dw)

		fsm = FSM(reset_state="RESET_CRC")
		self.submodules += fsm

		fsm.act("RESET_CRC",
			sink.ack.eq(0),
			self.crc.reset.eq(1),
			NextState("IDLE")
		)
		fsm.act("IDLE",
			sink.ack.eq(sink.stb),
			If(sink.stb & sink.sop,
				Record.connect(sink, source),
				self.crc.ce.eq(sink.ack),
				self.crc.d.eq(sink.d),
				NextState("COPY")
			)
		)
		fsm.act("COPY",
			Record.connect(sink, source),
			self.crc.ce.eq(sink.stb & sink.ack),
			self.crc.d.eq(sink.d),
			source.error.eq(sink.eop & self.crc.error),
			If(sink.stb & sink.ack & sink.eop,
				NextState("RESET_CRC")
			)
		)
		self.comb += self.busy.eq(~fsm.ongoing("IDLE"))

class CRC32Checker(CRCChecker):
	def __init__(self, layout):
		CRCChecker.__init__(self, CRC32, layout)
