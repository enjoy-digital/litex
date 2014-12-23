from lib.sata.common import *
from lib.sata.link.scrambler import Scrambler

class SATABIST(Module):
	def __init__(self, sector_size=512):
		self.sink = sink = Sink(command_rx_description(32))
		self.source = source = Source(command_tx_description(32))

		self.start = Signal()
		self.sector = Signal(48)
		self.count = Signal(4)
		self.done = Signal()
		self.ctrl_errors = Signal(32)
		self.data_errors = Signal(32)

		self.counter = counter = Counter(bits_sign=32)
		self.ctrl_error_counter = Counter(self.ctrl_errors, bits_sign=32)
		self.data_error_counter = Counter(self.data_errors, bits_sign=32)

		self.scrambler = scrambler = InsertReset(Scrambler())
		self.comb += [
			scrambler.reset.eq(counter.reset),
			scrambler.ce.eq(counter.ce)
		]

		self.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			self.done.eq(1),
			counter.reset.eq(1),
			If(self.start,
				self.ctrl_error_counter.reset.eq(1),
				self.data_error_counter.reset.eq(1),
				NextState("SEND_WRITE_CMD_AND_DATA")
			)
		)
		fsm.act("SEND_WRITE_CMD_AND_DATA",
			source.stb.eq(1),
			source.sop.eq((counter.value == 0)),
			source.eop.eq((counter.value == (sector_size//4*self.count)-1)),
			source.write.eq(1),
			source.sector.eq(self.sector),
			source.count.eq(self.count),
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
					self.ctrl_error_counter.ce.eq(1)
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
			source.count.eq(self.count),
			If(source.ack,
				NextState("WAIT_READ_ACK")
			)
		)
		fsm.act("WAIT_READ_ACK",
			counter.reset.eq(1),
			If(sink.stb & sink.read,
				If(~sink.read | ~sink.success | sink.failed,
					self.ctrl_error_counter.ce.eq(1)
				),
				NextState("RECEIVE_READ_DATA")
			)
		)
		fsm.act("RECEIVE_READ_DATA",
			sink.ack.eq(1),
			If(sink.stb,
				counter.ce.eq(1),
				If(sink.data != scrambler.value,
					self.data_error_counter.ce.eq(1)
				),
				If(sink.eop,
					NextState("IDLE")
				)
			)
		)
