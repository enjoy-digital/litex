from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.record import Record
from migen.actorlib.fifo import SyncFIFO, AsyncFIFO


class UART(Module, AutoCSR):
    def __init__(self, phy,
                 tx_fifo_depth=16,
                 rx_fifo_depth=16,
                 phy_cd="sys"):
        self._rxtx = CSR(8)
        self._txfull = CSRStatus()
        self._rxempty = CSRStatus()

        self.submodules.ev = EventManager()
        self.ev.tx = EventSourceProcess()
        self.ev.rx = EventSourceProcess()
        self.ev.finalize()

        # # #

        if phy_cd == "sys":
            tx_fifo = SyncFIFO([("data", 8)], tx_fifo_depth)
            rx_fifo = SyncFIFO([("data", 8)], rx_fifo_depth)
            # Generate TX IRQ when tx_fifo becomes empty
            tx_irq = tx_fifo.source.stb
        else:
            tx_fifo = ClockDomainsRenamer({"write": "sys", "read": phy_cd})(
                AsyncFIFO([("data", 8)], tx_fifo_depth))
            rx_fifo = ClockDomainsRenamer({"write": phy_cd, "read": "sys"})(
                AsyncFIFO([("data", 8)], rx_fifo_depth))
            # Generate TX IRQ when tx_fifo becomes non-full
            tx_irq = ~tx_fifo.sink.ack
        self.submodules += tx_fifo, rx_fifo
        self.comb += [
            tx_fifo.sink.stb.eq(self._rxtx.re),
            tx_fifo.sink.data.eq(self._rxtx.r),
            self._txfull.status.eq(~tx_fifo.sink.ack),
            Record.connect(tx_fifo.source, phy.sink),
            self.ev.tx.trigger.eq(tx_irq),

            Record.connect(phy.source, rx_fifo.sink),
            self._rxempty.status.eq(~rx_fifo.source.stb),
            self._rxtx.w.eq(rx_fifo.source.data),
            rx_fifo.source.ack.eq(self.ev.rx.clear),
            # Generate RX IRQ when rx_fifo becomes non-empty
            self.ev.rx.trigger.eq(~rx_fifo.source.stb),
        ]
