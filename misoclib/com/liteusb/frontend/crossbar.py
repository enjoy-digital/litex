from migen.fhdl.std import *
from migen.genlib.roundrobin import *
from migen.genlib.record import Record

from misoclib.com.liteusb.common import *

class LiteUSBCrossbar(Module):
    def __init__(self, masters, slave=None):
        if slave is None:
            slave = LiteUSBPipe(user_layout)
            self.slave = slave

        # masters --> slave arbitration
        self.submodules.rr = RoundRobin(len(masters))
        cases = {}
        for i, m in enumerate(masters):
            sop = Signal()
            eop = Signal()
            ongoing = Signal()
            self.comb += [
                sop.eq(m.source.stb & m.source.sop),
                eop.eq(m.source.stb & m.source.eop & m.source.ack),
            ]
            self.sync += ongoing.eq((sop | ongoing) & ~eop)
            self.comb += self.rr.request[i].eq(sop | ongoing)

            cases[i] = [Record.connect(masters[i].source, slave.source)]
        self.comb += Case(self.rr.grant, cases)

        # slave --> master demux
        cases = {}
        for i, m in enumerate(masters):
            cases[m.tag] = [Record.connect(slave.sink, masters[i].sink)]
        cases["default"] = [slave.sink.ack.eq(1)]
        self.comb += Case(slave.sink.dst, cases)
