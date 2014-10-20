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
		self.sink = Sink(layout, True)
		self.source = Source(layout, True)
		self.busy = Signal()

		###

		dw = flen(self.sink.d)
		self.submodules.crc = crc_class(dw)
		self.submodules.fsm = fsm = FSM(reset_state="IDLE")

		fsm.act("IDLE",
			self.crc.reset.eq(1),
			self.sink.ack.eq(1),
			If(self.sink.stb & self.sink.sop,
				self.sink.ack.eq(0),
				NextState("COPY"),
			)
		)
		fsm.act("COPY",
			self.crc.ce.eq(self.sink.stb & self.source.ack),
			self.crc.d.eq(self.sink.d),
			Record.connect(self.sink, self.source),
			self.source.eop.eq(0),
			If(self.sink.stb & self.sink.eop & self.source.ack,
				NextState("INSERT"),
			)
		)
		ratio = self.crc.width//dw
		cnt = Signal(max=ratio, reset=ratio-1)
		cnt_done = Signal()
		fsm.act("INSERT",
			self.source.stb.eq(1),
			chooser(self.crc.value, cnt, self.source.d, reverse=True),
			If(cnt_done,
				self.source.eop.eq(1),
				If(self.source.ack, NextState("IDLE"))
			)
		)
		self.comb += cnt_done.eq(cnt == 0)
		self.sync += \
			If(fsm.ongoing("IDLE"),
				cnt.eq(cnt.reset)
			).Elif(fsm.ongoing("INSERT") & ~cnt_done,
				cnt.eq(cnt - self.source.ack)
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
		Packets output with CRC and "discarded" set to 0
		on eop if CRC OK / set to 1 is CRC KO.
	"""
	def __init__(self, crc_class, layout):
		self.sink = Sink(layout, True)
		self.source = Source(layout, True)
		self.busy = Signal()

		###

		dw = flen(self.sink.d)
		self.submodules.crc = crc_class(dw)

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			self.crc.reset.eq(1),
			self.sink.ack.eq(self.sink.stb),
			If(self.sink.stb & self.sink.sop,
				self.sink.ack.eq(0),
				NextState("COPY")
			)
		)
		fsm.act("COPY",
			Record.connect(self.sink, self.source),
			self.crc.ce.eq(self.sink.stb & (self.sink.ack | self.sink.eop)),
			self.crc.d.eq(self.sink.d),
			If(self.sink.stb & self.sink.eop,
				self.sink.ack.eq(0),
				self.source.stb.eq(0),
				NextState("CHECK")
			)
		)
		fsm.act("CHECK",
			Record.connect(self.sink, self.source),
			self.source.discarded.eq(self.crc.error),
			If(self.source.stb & self.source.ack, NextState("IDLE"))
		)
		self.comb += self.busy.eq(~fsm.ongoing("IDLE"))

class CRC32Checker(CRCChecker):
	def __init__(self, layout):
		CRCChecker.__init__(self, CRC32, layout)
