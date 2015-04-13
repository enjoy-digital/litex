from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.record import Record
from migen.flow.actor import Sink, Source

class UART(Module, AutoCSR):
    def __init__(self, phy):
        self._rxtx = CSR(8)

        self.submodules.ev = EventManager()
        self.ev.tx = EventSourcePulse()
        self.ev.rx = EventSourcePulse()
        self.ev.finalize()
        ###
        self.sync += [
            If(self._rxtx.re,
                phy.sink.stb.eq(1),
                phy.sink.data.eq(self._rxtx.r),
            ).Elif(phy.sink.ack,
                phy.sink.stb.eq(0)
            ),
            If(phy.source.stb,
                self._rxtx.w.eq(phy.source.data)
            )
        ]
        self.comb += [
            self.ev.tx.trigger.eq(phy.sink.stb & phy.sink.ack),
            self.ev.rx.trigger.eq(phy.source.stb & phy.source.ack),
            phy.source.ack.eq(~self.ev.rx.pending)
        ]
