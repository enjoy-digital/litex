from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.core.link.scrambler import Scrambler

from migen.bank.description import *

class LiteSATABISTGenerator(Module):
    def __init__(self, user_port):
        self.start = Signal()
        self.sector = Signal(48)
        self.count = Signal(16)
        self.random = Signal()

        self.done = Signal()
        self.aborted = Signal()
        self.errors = Signal(32) # Note: Not used for writes

        ###

        source, sink = user_port.sink, user_port.source

        counter = Counter(32)
        self.submodules += counter

        scrambler = scrambler = InsertReset(Scrambler())
        self.submodules += scrambler
        self.comb += [
            scrambler.reset.eq(counter.reset),
            scrambler.ce.eq(counter.ce)
        ]

        self.fsm = fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
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
    def __init__(self, user_port):
        self.start = Signal()
        self.sector = Signal(48)
        self.count = Signal(16)
        self.random = Signal()

        self.done = Signal()
        self.aborted = Signal()
        self.errors = Signal(32)

        ###

        source, sink = user_port.sink, user_port.source

        counter = Counter(32)
        error_counter = Counter(32)
        self.submodules += counter, error_counter
        self.comb += self.errors.eq(error_counter.value)

        scrambler = InsertReset(Scrambler())
        self.submodules += scrambler
        self.comb += [
            scrambler.reset.eq(counter.reset),
            scrambler.ce.eq(counter.ce)
        ]

        self.fsm = fsm = FSM(reset_state="IDLE")
        self.submodules += self.fsm
        fsm.act("IDLE",
            self.done.eq(1),
            counter.reset.eq(1),
            If(self.start,
                error_counter.reset.eq(1),
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
                    error_counter.ce.eq(~sink.last)
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

        self.submodules += bist_unit

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
        loop_counter = Counter(8)
        self.submodules += fsm, loop_counter
        fsm.act("IDLE",
            self._done.status.eq(1),
            loop_counter.reset.eq(1),
            If(start,
                NextState("CHECK")
            )
        )
        fsm.act("CHECK",
            If(loop_counter.value < loops,
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
                loop_counter.ce.eq(1),
                NextState("CHECK")
            )
        )

        cycles_counter = Counter(32)
        self.submodules += cycles_counter
        self.sync += [
            cycles_counter.reset.eq(start),
            cycles_counter.ce.eq(~fsm.ongoing("IDLE")),
            self._cycles.status.eq(cycles_counter.value)
        ]

class LiteSATABISTIdentify(Module):
    def __init__(self, user_port):
        self.start = Signal()
        self.done  = Signal()

        fifo = SyncFIFO([("data", 32)], 512, buffered=True)
        self.submodules += fifo
        self.source = fifo.source

        ###

        source, sink = user_port.sink, user_port.source

        self.fsm = fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
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

        self.submodules += bist_identify
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
            generator = LiteSATABISTUnitCSR(generator)
            checker = LiteSATABISTUnitCSR(checker)
            identify = LiteSATABISTIdentifyCSR(identify)
        self.submodules.generator = generator
        self.submodules.checker = checker
        self.submodules.identify = identify
