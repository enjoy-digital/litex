from migen.fhdl.std import *
from migen.actorlib.structuring import *
from migen.genlib.fifo import SyncFIFO
from migen.genlib.fsm import FSM, NextState
from migen.actorlib.fifo import SyncFIFO as SyncFlowFIFO

from misoclib.com.litepcie.common import *
from misoclib.com.litepcie.core.packet.common import *
from misoclib.com.litepcie.core.switch.common import *


class Reordering(Module):
    def __init__(self, dw, max_pending_requests):
        self.sink = Sink(completion_layout(dw))
        self.source = Source(completion_layout(dw))

        self.req_we = Signal()
        self.req_tag = Signal(log2_int(max_pending_requests))

        # # #

        tag_buffer = SyncFIFO(log2_int(max_pending_requests), 2*max_pending_requests)
        self.submodules += tag_buffer
        self.comb += [
            tag_buffer.we.eq(self.req_we),
            tag_buffer.din.eq(self.req_tag)
        ]

        reorder_buffers = [SyncFlowFIFO(completion_layout(dw), 2*max_request_size//(dw//8), buffered=True)
            for i in range(max_pending_requests)]
        self.submodules += iter(reorder_buffers)

        # store incoming completion in "sink.tag" buffer
        cases = {}
        for i in range(max_pending_requests):
            cases[i] = [Record.connect(self.sink, reorder_buffers[i].sink)]
        cases["default"] = [self.sink.ack.eq(1)]
        self.comb += Case(self.sink.tag, cases)

        # read buffer according to tag_buffer order
        cases = {}
        for i in range(max_pending_requests):
            cases[i] = [Record.connect(reorder_buffers[i].source, self.source)]
        cases["default"] = []
        self.comb += [
            Case(tag_buffer.dout, cases),
            If(self.source.stb & self.source.eop & self.source.last,
                tag_buffer.re.eq(self.source.ack)
            )
        ]


class RequestController(Module):
    def __init__(self, dw, max_pending_requests, with_reordering=False):
        self.master_in = MasterInternalPort(dw)
        self.master_out = MasterInternalPort(dw)

        # # #

        req_sink, req_source = self.master_in.sink, self.master_out.sink
        cmp_sink, cmp_source = self.master_out.source, self.master_in.source

        tag_fifo = SyncFIFO(log2_int(max_pending_requests), max_pending_requests)
        self.submodules += tag_fifo

        info_mem = Memory(16, max_pending_requests)
        info_mem_wr_port = info_mem.get_port(write_capable=True)
        info_mem_rd_port = info_mem.get_port(async_read=False)
        self.specials += info_mem, info_mem_wr_port, info_mem_rd_port

        req_tag = Signal(max=max_pending_requests)
        self.sync += \
            If(tag_fifo.re,
                req_tag.eq(tag_fifo.dout)
            )

    # requests mgt
        req_fsm = FSM(reset_state="IDLE")
        self.submodules += req_fsm

        req_fsm.act("IDLE",
            req_sink.ack.eq(0),
            If(req_sink.stb & req_sink.sop & ~req_sink.we & tag_fifo.readable,
                tag_fifo.re.eq(1),
                NextState("SEND_READ")
            ).Elif(req_sink.stb & req_sink.sop & req_sink.we,
                NextState("SEND_WRITE")
            )
        )
        req_fsm.act("SEND_READ",
            Record.connect(req_sink, req_source),
            req_sink.ack.eq(0),
            req_source.tag.eq(req_tag),
            If(req_source.stb & req_source.eop & req_source.ack,
                NextState("UPDATE_INFO_MEM")
            )
        )
        req_fsm.act("SEND_WRITE",
            Record.connect(req_sink, req_source),
            req_source.tag.eq(32),
            If(req_source.stb & req_source.eop & req_source.ack,
                NextState("IDLE")
            )
        )
        req_fsm.act("UPDATE_INFO_MEM",
            info_mem_wr_port.we.eq(1),
            info_mem_wr_port.adr.eq(req_tag),
            info_mem_wr_port.dat_w[0:8].eq(req_sink.channel),
            info_mem_wr_port.dat_w[8:16].eq(req_sink.user_id),
            req_sink.ack.eq(1),
            NextState("IDLE")
        )


    # completions mgt
        if with_reordering:
            self.submodules.reordering = Reordering(dw, max_pending_requests)
            self.comb += [
                self.reordering.req_we.eq(info_mem_wr_port.we),
                self.reordering.req_tag.eq(info_mem_wr_port.adr),
                Record.connect(self.reordering.source, cmp_source)
            ]
            cmp_source = self.reordering.sink

        cmp_fsm = FSM(reset_state="INIT")
        self.submodules += cmp_fsm

        tag_cnt = Signal(max=max_pending_requests)
        inc_tag_cnt = Signal()
        self.sync += \
            If(inc_tag_cnt,
                tag_cnt.eq(tag_cnt+1)
            )

        cmp_fsm.act("INIT",
            inc_tag_cnt.eq(1),
            tag_fifo.we.eq(1),
            tag_fifo.din.eq(tag_cnt),
            If(tag_cnt == (max_pending_requests-1),
                NextState("IDLE")
            )
        )
        cmp_fsm.act("IDLE",
            cmp_sink.ack.eq(1),
            info_mem_rd_port.adr.eq(cmp_sink.tag),
            If(cmp_sink.stb & cmp_sink.sop,
                cmp_sink.ack.eq(0),
                NextState("COPY"),
            )
        )
        cmp_fsm.act("COPY",
            info_mem_rd_port.adr.eq(cmp_sink.tag),
            If(cmp_sink.stb & cmp_sink.eop & cmp_sink.last,
                cmp_sink.ack.eq(0),
                NextState("UPDATE_TAG_FIFO"),
            ).Else(
                Record.connect(cmp_sink, cmp_source),
                If(cmp_sink.stb & cmp_sink.eop & cmp_sink.ack,
                    NextState("IDLE")
                )
            ),
            cmp_source.channel.eq(info_mem_rd_port.dat_r[0:8]),
            cmp_source.user_id.eq(info_mem_rd_port.dat_r[8:16]),
        )
        cmp_fsm.act("UPDATE_TAG_FIFO",
            tag_fifo.we.eq(1),
            tag_fifo.din.eq(cmp_sink.tag),
            info_mem_rd_port.adr.eq(cmp_sink.tag),
            Record.connect(cmp_sink, cmp_source),
            If(cmp_sink.stb & cmp_sink.ack,
                NextState("IDLE")
            ),
            cmp_source.channel.eq(info_mem_rd_port.dat_r[0:8]),
            cmp_source.user_id.eq(info_mem_rd_port.dat_r[8:16]),
        )
