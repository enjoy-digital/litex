from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.fsm import FSM, NextState
from migen.actorlib.fifo import SyncFIFO as FIFO

from misoclib.com.litepcie.common import *
from misoclib.com.litepcie.core.packet.common import *
from misoclib.com.litepcie.frontend.dma.common import *


class DMAReader(Module, AutoCSR):
    def __init__(self, endpoint, port, table_depth=256):
        self.source = Source(dma_layout(endpoint.phy.dw))
        self._enable = CSRStorage()

        # # #

        enable = self._enable.storage

        max_words_per_request = max_request_size//(endpoint.phy.dw//8)
        max_pending_words = endpoint.max_pending_requests*max_words_per_request

        fifo_depth = 2*max_pending_words

    # Request generation
        # requests from table are splitted in chunks of "max_size"
        self.table = table = DMARequestTable(table_depth)
        splitter = InsertReset(DMARequestSplitter(endpoint.phy.max_request_size))
        self.submodules += table, splitter
        self.comb += splitter.reset.eq(~enable)
        self.comb += table.source.connect(splitter.sink)

    # Request FSM
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        request_ready = Signal()
        fsm.act("IDLE",
            If(request_ready,
                NextState("REQUEST"),
            )
        )
        fsm.act("REQUEST",
            port.source.stb.eq(1),
            port.source.channel.eq(port.channel),
            port.source.user_id.eq(splitter.source.user_id),
            port.source.sop.eq(1),
            port.source.eop.eq(1),
            port.source.we.eq(0),
            port.source.adr.eq(splitter.source.address),
            port.source.len.eq(splitter.source.length[2:]),
            port.source.req_id.eq(endpoint.phy.id),
            port.source.dat.eq(0),
            If(port.source.ack,
                splitter.source.ack.eq(1),
                NextState("IDLE"),
            )
        )

    # Data FIFO
        # issue read requests when enough space available in fifo
        fifo = InsertReset(FIFO(dma_layout(endpoint.phy.dw), fifo_depth, buffered=True))
        self.submodules += fifo
        self.comb += fifo.reset.eq(~enable)

        last_user_id = Signal(8, reset=255)
        self.sync += \
            If(port.sink.stb & port.sink.sop & port.sink.ack,
                last_user_id.eq(port.sink.user_id)
            )
        self.comb += [
            fifo.sink.stb.eq(port.sink.stb),
            fifo.sink.sop.eq(port.sink.sop & (port.sink.user_id != last_user_id)),
            fifo.sink.data.eq(port.sink.dat),
            port.sink.ack.eq(fifo.sink.ack | ~enable),
        ]
        self.comb += Record.connect(fifo.source, self.source)

        fifo_ready = fifo.fifo.level < (fifo_depth//2)
        self.comb += request_ready.eq(splitter.source.stb & fifo_ready)
