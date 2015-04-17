from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.fifo import SyncFIFOBuffered as SyncFIFO
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import chooser, displacer
from migen.flow.plumbing import Buffer

from misoclib.com.litepcie.common import *


def descriptor_layout(with_user_id=False):
    layout = [
        ("address",        32),
        ("length",        16)
    ]
    if with_user_id:
        layout += [("user_id",    8)]
    return EndpointDescription(layout, packetized=True)


class DMARequestTable(Module, AutoCSR):
    def __init__(self, depth):
        self.source = source = Source(descriptor_layout())

        aw = flen(source.address)
        lw = flen(source.length)

        self._value = CSRStorage(aw+lw)
        self._we = CSR()
        self._loop_prog_n = CSRStorage()
        self._index = CSRStatus(log2_int(depth))
        self._level = CSRStatus(log2_int(depth))
        self._flush = CSR()

        self.irq = Signal()

       # # #

    # CSR signals
        value = self._value.storage
        we = self._we.r & self._we.re
        loop_prog_n = self._loop_prog_n.storage
        index = self._index.status
        level = self._level.status
        flush = self._flush.r & self._flush.re

    # FIFO
        # instance
        fifo_layout = [("address", aw), ("length", lw), ("start", 1)]
        fifo = InsertReset(SyncFIFO(fifo_layout, depth))
        self.submodules += fifo
        self.comb += [
            fifo.reset.eq(flush),
            level.eq(fifo.level)
        ]

        # write part
        self.sync += [
            # in "loop" mode, each data output of the fifo is
            # written back
            If(loop_prog_n,
                fifo.din.address.eq(fifo.dout.address),
                fifo.din.length.eq(fifo.dout.length),
                fifo.din.start.eq(fifo.dout.start),
                fifo.we.eq(fifo.re)
            # in "program" mode, fifo input is connected
            # to registers
            ).Else(
                fifo.din.address.eq(value[:aw]),
                fifo.din.length.eq(value[aw:aw+lw]),
                fifo.din.start.eq(~fifo.readable),
                fifo.we.eq(we)
            )
        ]

        # read part
        self.comb += [
            source.stb.eq(fifo.readable),
            fifo.re.eq(source.stb & source.ack),
            source.address.eq(fifo.dout.address),
            source.length.eq(fifo.dout.length)
        ]

        # index
        # used by the software for synchronization in
        # "loop" mode
        self.sync += \
            If(flush,
                index.eq(0)
            ).Elif(source.stb & source.ack,
                If(fifo.dout.start,
                    index.eq(0)
                ).Else(
                    index.eq(index+1)
                )
            )

    # IRQ
        self.comb += self.irq.eq(source.stb & source.ack)


class DMARequestSplitter(Module, AutoCSR):
    def __init__(self, max_size, buffered=True):
        self.sink = sink = Sink(descriptor_layout())
        if buffered:
            self.submodules.buffer = Buffer(descriptor_layout(True))
            source = self.buffer.d
            self.source = self.buffer.q
        else:
            self.source = source = Source(descriptor_layout(True))

        # # #

        offset = Signal(32)
        clr_offset = Signal()
        inc_offset = Signal()
        self.sync += \
            If(clr_offset,
                offset.eq(0)
            ).Elif(inc_offset,
                offset.eq(offset + max_size)
            )
        user_id = Signal(8)
        self.sync += \
            If(sink.stb & sink.ack,
                user_id.eq(user_id+1)
            )

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        length = Signal(16)
        update_length = Signal()
        self.sync += If(update_length, length.eq(sink.length))

        fsm.act("IDLE",
            sink.ack.eq(1),
            clr_offset.eq(1),
            If(sink.stb,
                update_length.eq(1),
                sink.ack.eq(0),
                NextState("RUN")
            )
        )
        fsm.act("RUN",
            source.stb.eq(1),
            source.address.eq(sink.address + offset),
            source.user_id.eq(user_id),
            If((length - offset) > max_size,
                source.length.eq(max_size),
                inc_offset.eq(source.ack)
            ).Else(
                source.length.eq(length - offset),
                If(source.ack,
                    NextState("ACK")
                )
            )
        )
        fsm.act("ACK",
            sink.ack.eq(1),
            NextState("IDLE")
        )
