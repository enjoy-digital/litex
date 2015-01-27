from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import chooser
from migen.genlib.record import *
from migen.flow.actor import Sink, Source

from liteethernet.common import *
from liteethernet.ethmac.common import *

class PreambleInserter(Module):
	def __init__(self, d_w):
		self.sink = Sink(eth_description(d_w))
		self.source = Source(eth_description(d_w))

		###

		preamble = Signal(64, reset=eth_preamble)
		cnt_max = (64//d_w)-1
		cnt = Signal(max=cnt_max+1)
		clr_cnt = Signal()
		inc_cnt = Signal()

		self.sync += \
			If(clr_cnt,
				cnt.eq(0)
			).Elif(inc_cnt,
				cnt.eq(cnt+1)
			)

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			self.sink.ack.eq(1),
			clr_cnt.eq(1),
			If(self.sink.stb & self.sink.sop,
				self.sink.ack.eq(0),
				NextState("INSERT"),
			)
		)
		fsm.act("INSERT",
			self.source.stb.eq(1),
			self.source.sop.eq(cnt==0),
			chooser(preamble, cnt, self.source.d),
			If(cnt == cnt_max,
				If(self.source.ack, NextState("COPY"))
			).Else(
				inc_cnt.eq(self.source.ack)
			)
		)
		fsm.act("COPY",
			Record.connect(self.sink, self.source),
			self.source.sop.eq(0),

			If(self.sink.stb & self.sink.eop & self.source.ack,
				NextState("IDLE"),
			)
		)

class PreambleChecker(Module):
	def __init__(self, d_w):
		self.sink = Sink(eth_description(d_w))
		self.source = Source(eth_description(d_w))

		###

		preamble = Signal(64, reset=eth_preamble)
		cnt_max = (64//d_w) - 1
		cnt = Signal(max=cnt_max+1)
		clr_cnt = Signal()
		inc_cnt = Signal()

		self.sync += \
			If(clr_cnt,
				cnt.eq(0)
			).Elif(inc_cnt,
				cnt.eq(cnt+1)
			)

		discard = Signal()
		clr_discard = Signal()
		set_discard = Signal()

		self.sync += \
			If(clr_discard,
				discard.eq(0)
			).Elif(set_discard,
				discard.eq(1)
			)

		sop = Signal()
		clr_sop = Signal()
		set_sop = Signal()
		self.sync += \
			If(clr_sop,
				sop.eq(0)
			).Elif(set_sop,
				sop.eq(1)
			)

		ref = Signal(d_w)
		match = Signal()
		self.comb += [
			chooser(preamble, cnt, ref),
			match.eq(self.sink.d == ref)
		]

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			self.sink.ack.eq(1),
			clr_cnt.eq(1),
			clr_discard.eq(1),
			If(self.sink.stb & self.sink.sop,
				clr_cnt.eq(0),
				inc_cnt.eq(1),
				clr_discard.eq(0),
				set_discard.eq(~match),
				NextState("CHECK"),
			)
		)
		fsm.act("CHECK",
			self.sink.ack.eq(1),
			If(self.sink.stb,
				set_discard.eq(~match),
				If(cnt == cnt_max,
					If(discard | (~match),
						NextState("IDLE")
					).Else(
						set_sop.eq(1),
						NextState("COPY")
					)
				).Else(
					inc_cnt.eq(1)
				)
			)
		)
		fsm.act("COPY",
			Record.connect(self.sink, self.source),
			self.source.sop.eq(sop),
			clr_sop.eq(self.source.stb & self.source.ack),

			If(self.source.stb & self.source.eop & self.source.ack,
				NextState("IDLE"),
			)
		)
