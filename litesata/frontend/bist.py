from litesata.common import *
from litesata.core.link.scrambler import Scrambler

from migen.fhdl.decorators import ModuleDecorator
from migen.bank.description import *

class LiteSATABISTGenerator(Module):
	def __init__(self, sata_master_port):
		self.start = Signal()
		self.sector = Signal(48)
		self.count = Signal(16)
		self.random = Signal()

		self.done = Signal()
		self.aborted = Signal()
		self.errors = Signal(32) # Note: Not used for writes

		###

		source, sink = sata_master_port.source, sata_master_port.sink

		self.counter = counter = Counter(bits_sign=32)

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
				NextState("SEND_CMD_AND_DATA")
			)
		)
		self.comb += [
			source.sop.eq(counter.value == 0),
			source.eop.eq(counter.value == (logical_sector_size//4*self.count)-1),
			source.write.eq(1),
			source.sector.eq(self.sector),
			source.count.eq(self.count),
			If(self.random,
				source.data.eq(scrambler.value)
			).Else(
				source.data.eq(counter.value)
			)
		]
		fsm.act("SEND_CMD_AND_DATA",
			source.stb.eq(1),
			If(source.stb & source.ack,
				counter.ce.eq(1),
				If(source.eop,
					NextState("WAIT_ACK")
				)
			)
		)
		fsm.act("WAIT_ACK",
			sink.ack.eq(1),
			If(sink.stb,
				NextState("IDLE")
			)
		)
		self.sync += If(sink.stb & sink.ack, self.aborted.eq(sink.failed))

class LiteSATABISTChecker(Module):
	def __init__(self, sata_master_port):
		self.start = Signal()
		self.sector = Signal(48)
		self.count = Signal(16)
		self.random = Signal()

		self.done = Signal()
		self.aborted = Signal()
		self.errors = Signal(32)

		###

		source, sink = sata_master_port.source, sata_master_port.sink

		self.counter = counter = Counter(bits_sign=32)
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
			If(self.start,
				self.error_counter.reset.eq(1),
				NextState("SEND_CMD")
			)
		)
		self.comb += [
			source.sop.eq(1),
			source.eop.eq(1),
			source.read.eq(1),
			source.sector.eq(self.sector),
			source.count.eq(self.count),
		]
		fsm.act("SEND_CMD",
			source.stb.eq(1),
			If(source.ack,
				counter.reset.eq(1),
				NextState("WAIT_ACK")
			)
		)
		fsm.act("WAIT_ACK",
			If(sink.stb & sink.read,
				NextState("RECEIVE_DATA")
			)
		)
		expected_data = Signal(32)
		self.comb += \
			If(self.random,
				expected_data.eq(scrambler.value)
			).Else(
				expected_data.eq(counter.value)
			)
		fsm.act("RECEIVE_DATA",
			sink.ack.eq(1),
			If(sink.stb,
				counter.ce.eq(1),
				If(sink.data != expected_data,
					self.error_counter.ce.eq(~sink.last)
				),
				If(sink.eop,
					If(sink.last,
						NextState("IDLE")
					).Else(
						NextState("WAIT_ACK")
					)
				)
			)
		)
		self.sync += If(sink.stb & sink.ack, self.aborted.eq(sink.failed))

class LiteSATABISTUnitCSR(Module, AutoCSR):
	def __init__(self, bist_unit):
		self._start = CSR()
		self._sector = CSRStorage(48)
		self._count = CSRStorage(16)
		self._loops = CSRStorage(8)
		self._random = CSRStorage()

		self._done = CSRStatus()
		self._aborted = CSRStatus()
		self._errors = CSRStatus(32)
		self._cycles = CSRStatus(32)

		###

		self.bist_unit = bist_unit
		start = self._start.r & self._start.re
		done = self._done.status
		loops = self._loops.storage

		self.comb += [
			bist_unit.sector.eq(self._sector.storage),
			bist_unit.count.eq(self._count.storage),
			bist_unit.random.eq(self._random.storage),

			self._aborted.status.eq(bist_unit.aborted),
			self._errors.status.eq(bist_unit.errors)
		]

		self.fsm = fsm = FSM(reset_state="IDLE")
		self.loop_counter = Counter(bits_sign=8)
		fsm.act("IDLE",
			self._done.status.eq(1),
			self.loop_counter.reset.eq(1),
			If(start,
				NextState("CHECK")
			)
		)
		fsm.act("CHECK",
			If(self.loop_counter.value < loops,
				NextState("START")
			).Else(
				NextState("IDLE")
			)
		)
		fsm.act("START",
			bist_unit.start.eq(1),
			NextState("WAIT_DONE")
		)
		fsm.act("WAIT_DONE",
			If(bist_unit.done,
				self.loop_counter.ce.eq(1),
				NextState("CHECK")
			)
		)

		self.cycles_counter = Counter(self._cycles.status)
		self.sync += [
			self.cycles_counter.reset.eq(start),
			self.cycles_counter.ce.eq(~fsm.ongoing("IDLE"))
		]

class LiteSATABISTIdentify(Module):
	def __init__(self, sata_master_port):
		self.start = Signal()
		self.done  = Signal()

		self.fifo = fifo = SyncFIFO([("data", 32)], 512, buffered=True)
		self.source = self.fifo.source

		###

		source, sink = sata_master_port.source, sata_master_port.sink

		self.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			self.done.eq(1),
			If(self.start,
				NextState("SEND_CMD")
			)
		)
		self.comb += [
			source.sop.eq(1),
			source.eop.eq(1),
			source.identify.eq(1),
		]
		fsm.act("SEND_CMD",
			source.stb.eq(1),
			If(source.stb & source.ack,
				NextState("WAIT_ACK")
			)
		)
		fsm.act("WAIT_ACK",
			If(sink.stb & sink.identify,
				NextState("RECEIVE_DATA")
			)
		)
		self.comb += fifo.sink.data.eq(sink.data)
		fsm.act("RECEIVE_DATA",
			sink.ack.eq(fifo.sink.ack),
			If(sink.stb,
				fifo.sink.stb.eq(1),
				If(sink.eop,
					NextState("IDLE")
				)
			)
		)

class LiteSATABISTIdentifyCSR(Module, AutoCSR):
	def __init__(self, bist_identify):
		self._start = CSR()
		self._done = CSRStatus()
		self._source_stb = CSRStatus()
		self._source_ack = CSR()
		self._source_data = CSRStatus(32)

		###

		self.bist_identify = bist_identify
		self.comb += [
			bist_identify.start.eq(self._start.r & self._start.re),
			self._done.status.eq(bist_identify.done),

			self._source_stb.status.eq(bist_identify.source.stb),
			self._source_data.status.eq(bist_identify.source.data),
			bist_identify.source.ack.eq(self._source_ack.r & self._source_ack.re)
		]

class LiteSATABIST(Module, AutoCSR):
	def __init__(self, crossbar, with_csr=False):
		generator = LiteSATABISTGenerator(crossbar.get_port())
		checker = LiteSATABISTChecker(crossbar.get_port())
		identify = LiteSATABISTIdentify(crossbar.get_port())
		if with_csr:
			self.generator = LiteSATABISTUnitCSR(generator)
			self.checker = LiteSATABISTUnitCSR(checker)
			self.identify = LiteSATABISTIdentifyCSR(identify)
		else:
			self.generator = generator
			self.checker = checker
			self.identify = identify
