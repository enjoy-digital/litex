from lib.sata.common import *
from lib.sata.link.scrambler import Scrambler
from migen.bank.description import *

class SATABIST(Module):
	def __init__(self, sata_con):
		self.write = Signal()
		self.read = Signal()
		self.sector = Signal(48)
		self.count = Signal(16)
		self.loops = Signal(8)

		self.done = Signal()
		self.errors = Signal(32)

	###

		sink = sata_con.source
		source = sata_con.sink

		self.counter = counter = Counter(bits_sign=32)
		self.loops_counter = loops_counter = Counter(bits_sign=8)
		self.error_counter = Counter(self.errors, bits_sign=32)

		self.scrambler = scrambler = InsertReset(Scrambler())
		self.comb += [
			scrambler.reset.eq(counter.reset),
			scrambler.ce.eq(counter.ce)
		]

		self.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			self.done.eq(1),
			counter.reset.eq(1),
			loops_counter.reset.eq(1),
			If(self.write,
				self.error_counter.reset.eq(1),
				NextState("SEND_WRITE_CMD_AND_DATA")
			).Elif(self.read,
				self.error_counter.reset.eq(1),
				NextState("SEND_READ_CMD")
			)
		)
		fsm.act("SEND_WRITE_CMD_AND_DATA",
			source.stb.eq(1),
			source.sop.eq(counter.value == 0),
			source.eop.eq(counter.value == (logical_sector_size//4*self.count)-1),
			source.write.eq(1),
			source.sector.eq(self.sector),
			source.count.eq(self.count),
			source.data.eq(scrambler.value),
			If(source.stb & source.ack,
				counter.ce.eq(1),
				If(source.eop,
					NextState("WAIT_WRITE_ACK")
				)
			)
		)
		fsm.act("WAIT_WRITE_ACK",
			sink.ack.eq(1),
			If(sink.stb,
				loops_counter.ce.eq(1),
				If(loops_counter.value == (self.loops-1),
					NextState("IDLE")
				).Else(
					counter.reset.eq(1),
					NextState("SEND_WRITE_CMD_AND_DATA")
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
				NextState("RECEIVE_READ_DATA")
			)
		)
		fsm.act("RECEIVE_READ_DATA",
			sink.ack.eq(1),
			If(sink.stb,
				counter.ce.eq(1),
				If(sink.data != scrambler.value,
					self.error_counter.ce.eq(1)
				),
				If(sink.eop,
					If(sink.last,
						loops_counter.ce.eq(1),
						If(loops_counter.value == (self.loops-1),
							NextState("IDLE")
						).Else(
							NextState("SEND_READ_CMD")
						)
					).Else(
						NextState("WAIT_READ_ACK")
					)
				)
			)
		)

class SATABISTControl(Module, AutoCSR):
	def __init__(self, sata_bist):
		self._write = CSR()
		self._read = CSR()
		self._sector = CSRStorage(48)
		self._count = CSRStorage(16)
		self._loops = CSRStorage(8)

		self._done = CSRStatus()
		self._errors = CSRStatus(32)

		self.comb += [
			sata_bist.write.eq(self._write.r & self._write.re),
			sata_bist.read.eq(self._read.r & self._read.re),
			sata_bist.sector.eq(self._sector.storage),
			sata_bist.count.eq(self._count.storage),
			sata_bist.loops.eq(self._loops.storage),

			self._done.status.eq(sata_bist.done),
			self._errors.status.eq(sata_bist.errors)
		]
