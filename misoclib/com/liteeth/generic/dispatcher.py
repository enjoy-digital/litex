from migen.fhdl.std import *
from migen.genlib.record import *


class Dispatcher(Module):
    def __init__(self, source, sinks, one_hot=False):
        if len(sinks) == 0:
            self.sel = Signal()
        elif len(sinks) == 1:
            self.comb += Record.connect(source, sinks.pop())
            self.sel = Signal()
        else:
            if one_hot:
                self.sel = Signal(len(sinks))
            else:
                self.sel = Signal(max=len(sinks))
            ###
            sop = Signal()
            self.comb += sop.eq(source.stb & source.sop)
            sel = Signal(flen(self.sel))
            sel_r = Signal(flen(self.sel))
            self.sync += \
                If(sop,
                    sel_r.eq(self.sel)
                )
            self.comb += \
                If(sop,
                    sel.eq(self.sel)
                ).Else(
                    sel.eq(sel_r)
                )
            cases = {}
            for i, sink in enumerate(sinks):
                if one_hot:
                    idx = 2**i
                else:
                    idx = i
                cases[idx] = [Record.connect(source, sink)]
            cases["default"] = [source.ack.eq(1)]
            self.comb += Case(sel, cases)
