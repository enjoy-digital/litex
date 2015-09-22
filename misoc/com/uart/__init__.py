from migen import *
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.record import Record
from migen.actorlib.fifo import SyncFIFO, AsyncFIFO


def _get_uart_fifo(depth, sink_cd="sys", source_cd="sys"):
    if sink_cd != source_cd:
        fifo = AsyncFIFO([("data", 8)], depth)
        return ClockDomainsRenamer({"write": sink_cd, "read": source_cd})(fifo)
    else:
        return SyncFIFO([("data", 8)], depth)


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

        # TX
        tx_fifo = _get_uart_fifo(tx_fifo_depth, source_cd=phy_cd)
        self.submodules += tx_fifo

        self.comb += [
            tx_fifo.sink.stb.eq(self._rxtx.re),
            tx_fifo.sink.data.eq(self._rxtx.r),
            self._txfull.status.eq(~tx_fifo.sink.ack),
            Record.connect(tx_fifo.source, phy.sink),
            # Generate TX IRQ when tx_fifo becomes non-full
            self.ev.tx.trigger.eq(~tx_fifo.sink.ack)
        ]


        # RX
        rx_fifo = _get_uart_fifo(rx_fifo_depth, sink_cd=phy_cd)
        self.submodules += rx_fifo


        self.comb += [
            Record.connect(phy.source, rx_fifo.sink),
            self._rxempty.status.eq(~rx_fifo.source.stb),
            self._rxtx.w.eq(rx_fifo.source.data),
            rx_fifo.source.ack.eq(self.ev.rx.clear),
            # Generate RX IRQ when tx_fifo becomes non-empty
            self.ev.rx.trigger.eq(~rx_fifo.source.stb)
        ]
