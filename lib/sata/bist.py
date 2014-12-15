from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState

from lib.sata.common import *

class SATABIST(Module):
	def __init__(self, sector_size=512, max_count=1):
		self.sink = sink = Sink(command_rx_description(32))
		self.source = source = Source(command_tx_description(32))

		self.start = Signal()
		self.sector = Signal(48)
		self.done = Signal()
		self.errors = Signal(32)

		errors = Signal(32)
		inc_errors = Signal()
		self.sync += \
			If(self.start,
				errors.eq(0),
			).Elif(inc_errors,
				errors.eq(errors+1)
			)
		self.comb += self.errors.eq(errors)

		cnt = Signal(32)
		inc_cnt = Signal()
		clr_cnt = Signal()
		self.sync += \
			If(clr_cnt,
				cnt.eq(0),
			).Elif(inc_cnt,
				cnt.eq(cnt+1)
			)

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			self.done.eq(1),
			clr_cnt.eq(1),
			If(self.start,
				NextState("SEND_WRITE_CMD_AND_DATA")
			)
		)
		fsm.act("SEND_WRITE_CMD_AND_DATA",
			source.stb.eq(1),
			source.sop.eq((cnt==0)),
			source.eop.eq((cnt==(sector_size*max_count)//4-1)),
			source.write.eq(1),
			source.sector.eq(self.sector),
			source.count.eq(max_count),
			source.data.eq(cnt), #XXX use LFSR
			inc_cnt.eq(source.ack),
			If(source.stb & source.eop & source.ack,
				NextState("WAIT_WRITE_ACK")
			)
		)
		fsm.act("WAIT_WRITE_ACK",
			sink.ack.eq(1),
			If(sink.stb & sink.write,
				NextState("SEND_READ_CMD")
			)
		)
		fsm.act("SEND_READ_CMD",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			source.read.eq(1),
			source.sector.eq(self.sector),
			source.count.eq(max_count),
			If(source.ack,
				NextState("WAIT_READ_ACK")
			)
		)
		fsm.act("WAIT_READ_ACK",
			clr_cnt.eq(1),
			If(sink.stb & sink.read,
				NextState("RECEIVE_READ_DATA")
			)
		)
		fsm.act("RECEIVE_READ_DATA",
			sink.ack.eq(1),
			inc_cnt.eq(sink.stb),
			If(sink.stb & (sink.data != cnt), #XXX use LFSR
				inc_errors.eq(1)
			),
			If(sink.stb & sink.eop,
				NextState("IDLE")
			)
		)
