from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.record import Record
from migen.actorlib.fifo import FIFO


class UART(Module, AutoCSR):
    def __init__(self, phy,
                 tx_fifo_depth=16, tx_irq_condition="empty",
                 rx_fifo_depth=16, rx_irq_condition="non-empty",
                 phy_cd="sys"):
        self._rxtx = CSR(8)
        self._txfull = CSRStatus()
        self._rxempty = CSRStatus()

        self.submodules.ev = EventManager()
        self.ev.tx = EventSourceProcess()
        self.ev.rx = EventSourceProcess()
        self.ev.finalize()

        # # #

        # TX
        tx_fifo = FIFO([("data", 8)], tx_fifo_depth, source_cd=phy_cd)
        self.submodules += tx_fifo

        tx_irqs = {
            "empty": tx_fifo.source.stb,
            "non-full": ~tx_fifo.sink.ack
        }

        self.comb += [
            tx_fifo.sink.stb.eq(self._rxtx.re),
            tx_fifo.sink.data.eq(self._rxtx.r),
            self._txfull.status.eq(~tx_fifo.sink.ack),
            Record.connect(tx_fifo.source, phy.sink),
            self.ev.tx.trigger.eq(tx_irqs[tx_irq_condition])
        ]


        # RX
        rx_fifo = FIFO([("data", 8)], rx_fifo_depth, sink_cd=phy_cd)
        self.submodules += rx_fifo

        rx_irqs = {
            "non-empty": ~rx_fifo.source.stb,
            "full": rx_fifo.sink.ack
        }

        self.comb += [
            Record.connect(phy.source, rx_fifo.sink),
            self._rxempty.status.eq(~rx_fifo.source.stb),
            self._rxtx.w.eq(rx_fifo.source.data),
            rx_fifo.source.ack.eq(self.ev.rx.clear),
            self.ev.rx.trigger.eq(rx_irqs[rx_irq_condition])
        ]
