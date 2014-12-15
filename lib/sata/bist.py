from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState

from lib.sata.common import *
from lib.sata.link.scrambler import Scrambler

class SATABIST(Module):
	def __init__(self, sector_size=512, max_count=1):
		self.sink = sink = Sink(command_rx_description(32))
		self.source = source = Source(command_tx_description(32))

		self.start = Signal()
		self.sector = Signal(48)
		self.done = Signal()
		self.ctrl_errors = Signal(32)
		self.data_errors = Signal(32)

		counter = Counter(bits_sign=32)
		ctrl_error_counter = Counter(self.ctrl_errors, bits_sign=32)
		data_error_counter = Counter(self.data_errors, bits_sign=32)
		self.submodules += counter, data_error_counter, ctrl_error_counter

		scrambler = InsertReset(Scrambler())
		self.submodules += scrambler
		self.comb += [
			scrambler.reset.eq(counter.reset),
			scrambler.ce.eq(counter.ce)
		]

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			self.done.eq(1),
			counter.reset.eq(1),
			ctrl_error_counter.reset.eq(1),
			data_error_counter.reset.eq(1),
			If(self.start,
				NextState("SEND_WRITE_CMD_AND_DATA")
			)
		)
		fsm.act("SEND_WRITE_CMD_AND_DATA",
			source.stb.eq(1),
			source.sop.eq((counter.value == 0)),
			source.eop.eq((counter.value == (sector_size*max_count)//4-1)),
			source.write.eq(1),
			source.sector.eq(self.sector),
			source.count.eq(max_count),
			source.data.eq(scrambler.value),
			counter.ce.eq(source.ack),
			If(source.stb & source.eop & source.ack,
				NextState("WAIT_WRITE_ACK")
			)
		)
		fsm.act("WAIT_WRITE_ACK",
			sink.ack.eq(1),
			If(sink.stb,
				If(~sink.write | ~sink.success | sink.failed,
					ctrl_error_counter.ce.eq(1)
				),
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
			counter.reset.eq(1),
			If(sink.stb & sink.read,
				If(~sink.read | ~sink.success | sink.failed,
					ctrl_error_counter.ce.eq(1)
				),
				NextState("RECEIVE_READ_DATA")
			)
		)
		fsm.act("RECEIVE_READ_DATA",
			sink.ack.eq(1),
			If(sink.stb,
				counter.ce.eq(1),
				If(sink.data != scrambler.value,
					data_error_counter.ce.eq(1)
				),
				If(sink.eop,
					NextState("IDLE")
				)
			)
		)
