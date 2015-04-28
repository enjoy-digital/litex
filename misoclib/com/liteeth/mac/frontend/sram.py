from misoclib.com.liteeth.common import *

from migen.bank.description import *
from migen.bank.eventmanager import *


class LiteEthMACSRAMWriter(Module, AutoCSR):
    def __init__(self, dw, depth, nslots=2):
        self.sink = sink = Sink(eth_phy_description(dw))
        self.crc_error = Signal()

        slotbits = max(log2_int(nslots), 1)
        lengthbits = log2_int(depth*4)  # length in bytes

        self._slot = CSRStatus(slotbits)
        self._length = CSRStatus(lengthbits)

        self.submodules.ev = EventManager()
        self.ev.available = EventSourceLevel()
        self.ev.finalize()

        # # #

        # packet dropped if no slot available
        sink.ack.reset = 1

        # length computation
        increment = Signal(3)
        self.comb += \
            If(sink.last_be[3],
                increment.eq(1)
            ).Elif(sink.last_be[2],
                increment.eq(2)
            ).Elif(sink.last_be[1],
                increment.eq(3)
            ).Else(
                increment.eq(4)
            )
        counter = Counter(lengthbits, increment=increment)
        self.submodules += counter

        # slot computation
        slot = Counter(slotbits)
        self.submodules += slot

        ongoing = Signal()

        # status fifo
        fifo = SyncFIFO([("slot", slotbits), ("length", lengthbits)], nslots)
        self.submodules += fifo

        # fsm
        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            If(sink.stb & sink.sop,
                If(fifo.sink.ack,
                    ongoing.eq(1),
                    counter.ce.eq(1),
                    NextState("WRITE")
                )
            )
        )
        fsm.act("WRITE",
            counter.ce.eq(sink.stb),
            ongoing.eq(1),
            If(sink.stb & sink.eop,
                If((sink.error & sink.last_be) != 0,
                    NextState("DISCARD")
                ).Else(
                    NextState("TERMINATE")
                )
            )
        )
        fsm.act("DISCARD",
            counter.reset.eq(1),
            NextState("IDLE")
        )
        self.comb += [
            fifo.sink.slot.eq(slot.value),
            fifo.sink.length.eq(counter.value)
        ]
        fsm.act("TERMINATE",
            counter.reset.eq(1),
            slot.ce.eq(1),
            fifo.sink.stb.eq(1),
            NextState("IDLE")
        )
        self.comb += [
            fifo.source.ack.eq(self.ev.available.clear),
            self.ev.available.trigger.eq(fifo.source.stb),
            self._slot.status.eq(fifo.source.slot),
            self._length.status.eq(fifo.source.length),
        ]

        # memory
        mems = [None]*nslots
        ports = [None]*nslots
        for n in range(nslots):
            mems[n] = Memory(dw, depth)
            ports[n] = mems[n].get_port(write_capable=True)
            self.specials += ports[n]
        self.mems = mems

        cases = {}
        for n, port in enumerate(ports):
            cases[n] = [
                ports[n].adr.eq(counter.value[2:]),
                ports[n].dat_w.eq(sink.data),
                If(sink.stb & ongoing,
                    ports[n].we.eq(0xf)
                )
            ]
        self.comb += Case(slot.value, cases)


class LiteEthMACSRAMReader(Module, AutoCSR):
    def __init__(self, dw, depth, nslots=2):
        self.source = source = Source(eth_phy_description(dw))

        slotbits = max(log2_int(nslots), 1)
        lengthbits = log2_int(depth*4)  # length in bytes
        self.lengthbits = lengthbits

        self._start = CSR()
        self._ready = CSRStatus()
        self._slot = CSRStorage(slotbits)
        self._length = CSRStorage(lengthbits)

        self.submodules.ev = EventManager()
        self.ev.done = EventSourcePulse()
        self.ev.finalize()

        # # #

        # command fifo
        fifo = SyncFIFO([("slot", slotbits), ("length", lengthbits)], nslots)
        self.submodules += fifo
        self.comb += [
            fifo.sink.stb.eq(self._start.re),
            fifo.sink.slot.eq(self._slot.storage),
            fifo.sink.length.eq(self._length.storage),
            self._ready.status.eq(fifo.sink.ack)
        ]

        # length computation
        self.submodules.counter = counter = Counter(lengthbits, increment=4)

        # fsm
        first = Signal()
        last  = Signal()
        last_d = Signal()

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            counter.reset.eq(1),
            If(fifo.source.stb,
                NextState("CHECK")
            )
        )
        fsm.act("CHECK",
            If(~last_d,
                NextState("SEND"),
            ).Else(
                NextState("END"),
            )
        )
        length_lsb = fifo.source.length[0:2]
        self.comb += [
            If(last,
                If(length_lsb == 3,
                    source.last_be.eq(0b0010)
                ).Elif(length_lsb == 2,
                    source.last_be.eq(0b0100)
                ).Elif(length_lsb == 1,
                    source.last_be.eq(0b1000)
                ).Else(
                    source.last_be.eq(0b0001)
                )
            )
        ]
        fsm.act("SEND",
            source.stb.eq(1),
            source.sop.eq(first),
            source.eop.eq(last),
            If(source.ack,
                counter.ce.eq(~last),
                NextState("CHECK")
            )
        )
        fsm.act("END",
            fifo.source.ack.eq(1),
            self.ev.done.trigger.eq(1),
            NextState("IDLE")
        )

        # first/last computation
        self.sync += [
            If(fsm.ongoing("IDLE"),
                first.eq(1)
            ).Elif(source.stb & source.ack,
                first.eq(0)
            )
        ]
        self.comb += last.eq((counter.value + 4) >= fifo.source.length)
        self.sync += last_d.eq(last)

        # memory
        rd_slot = fifo.source.slot

        mems = [None]*nslots
        ports = [None]*nslots
        for n in range(nslots):
            mems[n] = Memory(dw, depth)
            ports[n] = mems[n].get_port()
            self.specials += ports[n]
        self.mems = mems

        cases = {}
        for n, port in enumerate(ports):
            self.comb += ports[n].adr.eq(counter.value[2:])
            cases[n] = [source.data.eq(port.dat_r)]
        self.comb += Case(rd_slot, cases)


class LiteEthMACSRAM(Module, AutoCSR):
    def __init__(self, dw, depth, nrxslots, ntxslots):
        self.submodules.writer = LiteEthMACSRAMWriter(dw, depth, nrxslots)
        self.submodules.reader = LiteEthMACSRAMReader(dw, depth, ntxslots)
        self.submodules.ev = SharedIRQ(self.writer.ev, self.reader.ev)
        self.sink, self.source = self.writer.sink, self.reader.source
