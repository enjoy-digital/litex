from misoclib.com.liteeth.common import *


class LiteEthMACPreambleInserter(Module):
    def __init__(self, dw):
        self.sink = Sink(eth_phy_description(dw))
        self.source = Source(eth_phy_description(dw))

        # # #

        preamble = Signal(64, reset=eth_preamble)
        cnt_max = (64//dw)-1
        cnt = Signal(max=cnt_max+1)
        clr_cnt = Signal()
        inc_cnt = Signal()

        self.sync += \
            If(clr_cnt,
                cnt.eq(0)
            ).Elif(inc_cnt,
                cnt.eq(cnt+1)
            )

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
        fsm.act("IDLE",
            self.sink.ack.eq(1),
            clr_cnt.eq(1),
            If(self.sink.stb & self.sink.sop,
                self.sink.ack.eq(0),
                NextState("INSERT"),
            )
        )
        fsm.act("INSERT",
            self.source.stb.eq(1),
            self.source.sop.eq(cnt == 0),
            chooser(preamble, cnt, self.source.data),
            If(cnt == cnt_max,
                If(self.source.ack, NextState("COPY"))
            ).Else(
                inc_cnt.eq(self.source.ack)
            )
        )

        self.comb += [
            self.source.data.eq(self.sink.data),
            self.source.last_be.eq(self.sink.last_be)
        ]
        fsm.act("COPY",
            Record.connect(self.sink, self.source, leave_out=set(["data", "last_be"])),
            self.source.sop.eq(0),

            If(self.sink.stb & self.sink.eop & self.source.ack,
                NextState("IDLE"),
            )
        )


class LiteEthMACPreambleChecker(Module):
    def __init__(self, dw):
        self.sink = Sink(eth_phy_description(dw))
        self.source = Source(eth_phy_description(dw))

        # # #

        preamble = Signal(64, reset=eth_preamble)
        cnt_max = (64//dw) - 1
        cnt = Signal(max=cnt_max+1)
        clr_cnt = Signal()
        inc_cnt = Signal()

        self.sync += \
            If(clr_cnt,
                cnt.eq(0)
            ).Elif(inc_cnt,
                cnt.eq(cnt+1)
            )

        discard = Signal()
        clr_discard = Signal()
        set_discard = Signal()

        self.sync += \
            If(clr_discard,
                discard.eq(0)
            ).Elif(set_discard,
                discard.eq(1)
            )

        sop = Signal()
        clr_sop = Signal()
        set_sop = Signal()
        self.sync += \
            If(clr_sop,
                sop.eq(0)
            ).Elif(set_sop,
                sop.eq(1)
            )

        ref = Signal(dw)
        match = Signal()
        self.comb += [
            chooser(preamble, cnt, ref),
            match.eq(self.sink.data == ref)
        ]

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            self.sink.ack.eq(1),
            clr_cnt.eq(1),
            clr_discard.eq(1),
            If(self.sink.stb & self.sink.sop,
                clr_cnt.eq(0),
                inc_cnt.eq(1),
                clr_discard.eq(0),
                set_discard.eq(~match),
                NextState("CHECK"),
            )
        )
        fsm.act("CHECK",
            self.sink.ack.eq(1),
            If(self.sink.stb,
                set_discard.eq(~match),
                If(cnt == cnt_max,
                    If(discard | (~match),
                        NextState("IDLE")
                    ).Else(
                        set_sop.eq(1),
                        NextState("COPY")
                    )
                ).Else(
                    inc_cnt.eq(1)
                )
            )
        )
        self.comb += [
            self.source.data.eq(self.sink.data),
            self.source.last_be.eq(self.sink.last_be)
        ]
        fsm.act("COPY",
            Record.connect(self.sink, self.source, leave_out=set(["data", "last_be"])),
            self.source.sop.eq(sop),
            clr_sop.eq(self.source.stb & self.source.ack),

            If(self.source.stb & self.source.eop & self.source.ack,
                NextState("IDLE"),
            )
        )
