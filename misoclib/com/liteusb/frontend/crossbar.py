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
        sources = [master.source for master in masters]
        self.submodules.arbiter = Arbiter(sources, slave.source)

        # slave --> master demux
        cases = {}
        for i, m in enumerate(masters):
            cases[m.tag] = [Record.connect(slave.sink, masters[i].sink)]
        cases["default"] = [slave.sink.ack.eq(1)]
        self.comb += Case(slave.sink.dst, cases)
