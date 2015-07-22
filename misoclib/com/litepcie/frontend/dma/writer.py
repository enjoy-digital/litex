from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.fifo import SyncFIFOBuffered as SyncFIFO
from migen.genlib.fsm import FSM, NextState

from misoclib.com.litepcie.common import *
from misoclib.com.litepcie.core.packet.common import *
from misoclib.com.litepcie.frontend.dma.common import *


class DMAWriter(Module, AutoCSR):
    def __init__(self, endpoint, port, table_depth=256):
        self.sink = sink = Sink(dma_layout(endpoint.phy.dw))
        self._enable = CSRStorage()

       # # #

        enable = self._enable.storage

        max_words_per_request = max_request_size//(endpoint.phy.dw//8)
        fifo_depth = 4*max_words_per_request

    # Data FIFO
        # store data until we have enough data to issue a
        # write request
        fifo = InsertReset(SyncFIFO(endpoint.phy.dw, fifo_depth))
        self.submodules += fifo
        self.comb += [
            fifo.we.eq(sink.stb & enable),
            sink.ack.eq(fifo.writable & sink.stb & enable),
            fifo.din.eq(sink.data),
            fifo.reset.eq(~enable)
        ]

    # Request generation
        # requests from table are splitted in chunks of "max_size"
        self.table = table = DMARequestTable(table_depth)
        splitter = InsertReset(DMARequestSplitter(endpoint.phy.max_payload_size))
        self.submodules += table, splitter
        self.comb += splitter.reset.eq(~enable)
        self.comb += table.source.connect(splitter.sink)

    # Request FSM
        cnt = Signal(max=(2**flen(endpoint.phy.max_payload_size))/8)
        clr_cnt = Signal()
        inc_cnt = Signal()
        self.sync += \
            If(clr_cnt,
                cnt.eq(0)
            ).Elif(inc_cnt,
                cnt.eq(cnt + 1)
            )

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        request_ready = Signal()
        fsm.act("IDLE",
            clr_cnt.eq(1),
            If(request_ready,
                NextState("REQUEST"),
            )
        )
        fsm.act("REQUEST",
            inc_cnt.eq(port.source.stb & port.source.ack),

            port.source.stb.eq(1),
            port.source.channel.eq(port.channel),
            port.source.user_id.eq(splitter.source.user_id),
            port.source.sop.eq(cnt == 0),
            port.source.eop.eq(cnt == splitter.source.length[3:]-1),
            port.source.we.eq(1),
            port.source.adr.eq(splitter.source.address),
            port.source.req_id.eq(endpoint.phy.id),
            port.source.tag.eq(0),
            port.source.len.eq(splitter.source.length[2:]),
            port.source.dat.eq(fifo.dout),

            If(port.source.ack,
                fifo.re.eq(1),
                If(port.source.eop,
                    splitter.source.ack.eq(1),
                    NextState("IDLE"),
                )
            )
        )

        fifo_ready = fifo.level >= splitter.source.length[3:]
        self.sync += request_ready.eq(splitter.source.stb & fifo_ready)
