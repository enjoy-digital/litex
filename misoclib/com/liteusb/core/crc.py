from collections import OrderedDict
from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState
from migen.genlib.record import *
from migen.genlib.misc import chooser, optree
from migen.flow.actor import Sink, Source
from migen.actorlib.fifo import SyncFIFO

from misoclib.com.liteusb.common import *


class CRCEngine(Module):
    """Cyclic Redundancy Check Engine

    Compute next CRC value from last CRC value and data input using
    an optimized asynchronous LFSR.

    Parameters
    ----------
    dat_width : int
        Width of the data bus.
    width : int
        Width of the CRC.
    polynom : int
        Polynom of the CRC (ex: 0x04C11DB7 for IEEE 802.3 CRC)

    Attributes
    ----------
    d : in
        Data input.
    last : in
        last CRC value.
    next :
        next CRC value.
    """
    def __init__(self, dat_width, width, polynom):
        self.d = Signal(dat_width)
        self.last = Signal(width)
        self.next = Signal(width)

        # # #

        def _optimize_eq(l):
            """
            Replace even numbers of XORs in the equation
            with an equivalent XOR
            """
            d = OrderedDict()
            for e in l:
                if e in d:
                    d[e] += 1
                else:
                    d[e] = 1
            r = []
            for key, value in d.items():
                if value%2 != 0:
                    r.append(key)
            return r

        # compute and optimize CRC's LFSR
        curval = [[("state", i)] for i in range(width)]
        for i in range(dat_width):
            feedback = curval.pop() + [("din", i)]
            for j in range(width-1):
                if (polynom & (1<<(j+1))):
                    curval[j] += feedback
                curval[j] = _optimize_eq(curval[j])
            curval.insert(0, feedback)

        # implement logic
        for i in range(width):
            xors = []
            for t, n in curval[i]:
                if t == "state":
                    xors += [self.last[n]]
                elif t == "din":
                    xors += [self.d[n]]
            self.comb += self.next[i].eq(optree("^", xors))


@DecorateModule(InsertReset)
@DecorateModule(InsertCE)
class CRC32(Module):
    """IEEE 802.3 CRC

    Implement an IEEE 802.3 CRC generator/checker.

    Parameters
    ----------
    dat_width : int
        Width of the data bus.

    Attributes
    ----------
    d : in
        Data input.
    value : out
        CRC value (used for generator).
    error : out
        CRC error (used for checker).
    """
    width = 32
    polynom = 0x04C11DB7
    init = 2**width-1
    check = 0xC704DD7B
    def __init__(self, dat_width):
        self.d = Signal(dat_width)
        self.value = Signal(self.width)
        self.error = Signal()

        # # #

        self.submodules.engine = CRCEngine(dat_width, self.width, self.polynom)
        reg = Signal(self.width, reset=self.init)
        self.sync += reg.eq(self.engine.next)
        self.comb += [
            self.engine.d.eq(self.d),
            self.engine.last.eq(reg),

            self.value.eq(~reg[::-1]),
            self.error.eq(self.engine.next != self.check)
        ]


class CRCInserter(Module):
    """CRC Inserter

    Append a CRC at the end of each packet.

    Parameters
    ----------
    layout : layout
        Layout of the dataflow.

    Attributes
    ----------
    sink : in
        Packets input without CRC.
    source : out
        Packets output with CRC.
    """
    def __init__(self, crc_class, layout):
        self.sink = sink = Sink(layout)
        self.source = source = Source(layout)
        self.busy = Signal()

        # # #

        dw = flen(sink.d)
        crc = crc_class(dw)
        fsm = FSM(reset_state="IDLE")
        self.submodules += crc, fsm

        fsm.act("IDLE",
            crc.reset.eq(1),
            sink.ack.eq(1),
            If(sink.stb & sink.sop,
                sink.ack.eq(0),
                NextState("COPY"),
            )
        )
        fsm.act("COPY",
            crc.ce.eq(sink.stb & source.ack),
            crc.d.eq(sink.d),
            Record.connect(sink, source),
            source.eop.eq(0),
            If(sink.stb & sink.eop & source.ack,
                NextState("INSERT"),
            )
        )
        ratio = crc.width//dw
        if ratio > 1:
            cnt = Signal(max=ratio, reset=ratio-1)
            cnt_done = Signal()
            fsm.act("INSERT",
                source.stb.eq(1),
                chooser(crc.value, cnt, source.d, reverse=True),
                If(cnt_done,
                    source.eop.eq(1),
                    If(source.ack, NextState("IDLE"))
                )
            )
            self.comb += cnt_done.eq(cnt == 0)
            self.sync += \
                If(fsm.ongoing("IDLE"),
                    cnt.eq(cnt.reset)
                ).Elif(fsm.ongoing("INSERT") & ~cnt_done,
                    cnt.eq(cnt - source.ack)
                )
        else:
            fsm.act("INSERT",
                source.stb.eq(1),
                source.eop.eq(1),
                source.d.eq(crc.value),
                If(source.ack, NextState("IDLE"))
            )
        self.comb += self.busy.eq(~fsm.ongoing("IDLE"))


class CRC32Inserter(CRCInserter):
    def __init__(self, layout):
        CRCInserter.__init__(self, CRC32, layout)


class CRCChecker(Module):
    """CRC Checker

    Check CRC at the end of each packet.

    Parameters
    ----------
    layout : layout
        Layout of the dataflow.

    Attributes
    ----------
    sink : in
        Packets input with CRC.
    source : out
        Packets output without CRC and "error" set to 0
        on eop when CRC OK / set to 1 when CRC KO.
    """
    def __init__(self, crc_class, layout):
        self.sink = sink = Sink(layout)
        self.source = source = Source(layout)
        self.busy = Signal()

        # # #

        dw = flen(sink.d)
        crc = crc_class(dw)
        self.submodules += crc
        ratio = crc.width//dw

        error = Signal()
        fifo = InsertReset(SyncFIFO(layout, ratio + 1))
        self.submodules += fifo

        fsm = FSM(reset_state="RESET")
        self.submodules += fsm

        fifo_in = Signal()
        fifo_out = Signal()
        fifo_full = Signal()

        self.comb += [
            fifo_full.eq(fifo.fifo.level == ratio),
            fifo_in.eq(sink.stb & (~fifo_full | fifo_out)),
            fifo_out.eq(source.stb & source.ack),

            Record.connect(sink, fifo.sink),
            fifo.sink.stb.eq(fifo_in),
            self.sink.ack.eq(fifo_in),

            source.stb.eq(sink.stb & fifo_full),
            source.sop.eq(fifo.source.sop),
            source.eop.eq(sink.eop),
            fifo.source.ack.eq(fifo_out),
            source.payload.eq(fifo.source.payload),

            source.error.eq(sink.error | crc.error),
        ]

        fsm.act("RESET",
            crc.reset.eq(1),
            fifo.reset.eq(1),
            NextState("IDLE"),
        )
        fsm.act("IDLE",
            crc.d.eq(sink.d),
            If(sink.stb & sink.sop & sink.ack,
                crc.ce.eq(1),
                NextState("COPY")
            )
        )
        fsm.act("COPY",
            crc.d.eq(sink.d),
            If(sink.stb & sink.ack,
                crc.ce.eq(1),
                If(sink.eop,
                    NextState("RESET")
                )
            )
        )
        self.comb += self.busy.eq(~fsm.ongoing("IDLE"))


class CRC32Checker(CRCChecker):
    def __init__(self, layout):
        CRCChecker.__init__(self, CRC32, layout)


class LiteUSBCRC32(Module):
    def __init__(self, tag):
        self.tag = tag

        self.submodules.inserter = CRC32Inserter(user_layout)
        self.submodules.checker = CRC32Checker(user_layout)

        self.dma_sink = self.inserter.sink
        self.dma_source = self.checker.source

        self.sink = self.checker.sink
        self.source = self.inserter.source
