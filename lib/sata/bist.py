from lib.sata.common import *
from lib.sata.link.scrambler import Scrambler

from migen.fhdl.decorators import ModuleDecorator
from migen.bank.description import *

class SATABISTGenerator(Module):
	def __init__(self, sata_master_port):
		self.start = Signal()
		self.sector = Signal(48)
		self.count = Signal(16)
		self.loops = Signal(8)
		self.random = Signal()

		self.done = Signal()
		self.errors = Signal(32) # Note: Not used for writes

		###

		source, sink = sata_master_port.source, sata_master_port.sink

		self.counter = counter = Counter(bits_sign=32)
		self.loops_counter = loops_counter = Counter(bits_sign=8)

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
				loops_counter.ce.eq(1),
				If(loops_counter.value == (self.loops-1),
					NextState("IDLE")
				).Else(
					counter.reset.eq(1),
					NextState("SEND_CMD_AND_DATA")
				)
			)
		)

class SATABISTChecker(Module):
	def __init__(self, sata_master_port):
		self.start = Signal()
		self.sector = Signal(48)
		self.count = Signal(16)
		self.loops = Signal(8)
		self.random = Signal()

		self.done = Signal()
		self.errors = Signal(32)

		###

		source, sink = sata_master_port.source, sata_master_port.sink

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
					self.error_counter.ce.eq(1)
				),
				If(sink.eop,
					If(sink.last,
						loops_counter.ce.eq(1),
						If(loops_counter.value == (self.loops-1),
							NextState("IDLE")
						).Else(
							NextState("SEND_CMD")
						)
					).Else(
						NextState("WAIT_ACK")
					)
				)
			)
		)

class SATABISTControl(Module, AutoCSR):
	def __init__(self, bist_unit):
		self._start = CSR()
		self._sector = CSRStorage(48)
		self._count = CSRStorage(16)
		self._random = CSRStorage()
		self._loops = CSRStorage(8)
		self._done = CSRStatus()
		self._errors = CSRStatus(32)

		###
		self.bist_unit = bist_unit
		self.comb += [
			bist_unit.start.eq(self._start.r & self._start.re),
			bist_unit.sector.eq(self._sector.storage),
			bist_unit.count.eq(self._count.storage),
			bist_unit.loops.eq(self._loops.storage),
			bist_unit.random.eq(self._random.storage),

			self._done.status.eq(bist_unit.done),
			self._errors.status.eq(bist_unit.errors)
		]

class SATABIST(Module, AutoCSR):
	def __init__(self, sata_master_ports, with_control=False):
		generator = SATABISTGenerator(sata_master_ports[0])
		checker = SATABISTChecker(sata_master_ports[1])
		if with_control:
			self.generator = SATABISTControl(generator)
			self.checker = SATABISTControl(checker)
		else:
			self.generator = generator
			self.checker = checker
