from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.fifo import SyncFIFOBuffered

from misoclib.com.liteusb.common import *


class LiteUSBUART(Module, AutoCSR):
    def __init__(self, tag, fifo_depth=64):
        self.tag = tag

        self._rxtx = CSR(8)

        self.submodules.ev = EventManager()
        self.ev.tx = EventSourcePulse()
        self.ev.rx = EventSourceLevel()
        self.ev.finalize()

        self.source = source = Source(user_layout)
        self.sink = sink = Sink(user_layout)

        # # #

        # TX
        tx_start = self._rxtx.re
        tx_done = self.ev.tx.trigger

        self.sync += \
            If(tx_start,
                source.stb.eq(1),
                source.d.eq(self._rxtx.r),
            ).Elif(tx_done,
                source.stb.eq(0)
            )

        self.comb += [
            source.sop.eq(1),
            source.eop.eq(1),
            source.length.eq(1),
            source.dst.eq(self.tag),
            tx_done.eq(source.stb & source.ack),
        ]

        # RX
        rx_available = self.ev.rx.trigger

        rx_fifo = SyncFIFOBuffered(8, fifo_depth)
        self.submodules += rx_fifo
        self.comb += [
            rx_fifo.we.eq(sink.stb),
            sink.ack.eq(sink.stb & rx_fifo.writable),
            rx_fifo.din.eq(sink.d),

            rx_available.eq(rx_fifo.readable),
            rx_fifo.re.eq(self.ev.rx.clear),
            self._rxtx.w.eq(rx_fifo.dout)
        ]
