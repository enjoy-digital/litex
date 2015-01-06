from lib.sata.common import *
from lib.sata.link.scrambler import Scrambler
from migen.bank.description import *

class SATABISTUnit(Module):
	def __init__(self, sata_con):
		sink = sata_con.source
		source = sata_con.sink

		self.start = Signal()
		self.write_only = Signal()
		self.read_only = Signal()
		self.sector = Signal(48)
		self.count = Signal(16)
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
				If(self.read_only,
					NextState("SEND_READ_CMD")
				).Else(
					NextState("SEND_WRITE_CMD_AND_DATA")
				)
			)
		)
		fsm.act("SEND_WRITE_CMD_AND_DATA",
			source.stb.eq(1),
			source.sop.eq((counter.value == 0)),
			source.eop.eq((counter.value == (logical_sector_size//4*self.count)-1)),
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
				If(self.write_only,
					NextState("IDLE")
				).Else(
					NextState("SEND_READ_CMD")
				)
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
				counter.reset.eq(1),
				NextState("WAIT_READ_ACK")
			)
		)
		fsm.act("WAIT_READ_ACK",
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
					If(sink.last,
						NextState("IDLE")
					).Else(
						NextState("WAIT_READ_ACK")
					)
				)
			)
		)

class SATABIST(Module, AutoCSR):
	def __init__(self, sata_con):
		self._start = CSR()
		self._start_sector = CSRStorage(48)
		self._count = CSRStorage(4)
		self._write_only = CSRStorage()
		self._read_only = CSRStorage()

		self._stop = CSRStorage()

		self._sector = CSRStatus(48)
		self._errors = CSRStatus(32)

		start = self._start.r & self._start.re
		start_sector = self._start_sector.storage
		count = self._count.storage
		stop = self._stop.storage

		compute = Signal()

		write_only = self._write_only.storage
		read_only = self._read_only.storage
		sector = self._sector.status
		errors = self._errors.status

		###

		self.unit = SATABISTUnit(sata_con)
		self.comb += [
			self.unit.write_only.eq(write_only),
			self.unit.read_only.eq(read_only),
			self.unit.sector.eq(sector),
			self.unit.count.eq(count)
		]

		self.fsm = fsm = FSM(reset_state="IDLE")

		# FSM
		fsm.act("IDLE",
			If(start,
				NextState("START")
			)
		)
		fsm.act("START",
			self.unit.start.eq(1),
			NextState("WAIT_DONE")
		)
		fsm.act("WAIT_DONE",
			If(self.unit.done,
				NextState("COMPUTE")
			).Elif(stop,
				NextState("IDLE")
			)
		)
		fsm.act("COMPUTE",
			compute.eq(1),
			NextState("START")
		)

		self.sync += [
			If(start,
				errors.eq(0),
				sector.eq(start_sector)
			).Elif(compute,
				errors.eq(errors + self.unit.data_errors),
				sector.eq(sector + count)
			)
		]
