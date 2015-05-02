from misoclib.com.liteeth.common import *


class LiteEthMACPaddingInserter(Module):
    def __init__(self, dw, padding):
        self.sink = sink = Sink(eth_phy_description(dw))
        self.source = source = Source(eth_phy_description(dw))

        # # #

        padding_limit = math.ceil(padding/(dw/8))-1

        self.submodules.counter = counter = Counter(16, reset=1)
        counter_done = Signal()
        self.comb += [
            counter.reset.eq(sink.stb & sink.sop & sink.ack),
            counter.ce.eq(source.stb & source.ack),
            counter_done.eq(counter.value >= padding_limit),
        ]

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            Record.connect(sink, source),
            If(source.stb & source.ack,
                counter.ce.eq(1),
                If(sink.eop,
                    If(~counter_done,
                        source.eop.eq(0),
                        NextState("PADDING")
                    )
                )
            )
        )
        fsm.act("PADDING",
            source.stb.eq(1),
            source.eop.eq(counter_done),
            source.data.eq(0),
            If(source.ack,
                If(counter_done,
                    NextState("IDLE")
                )
            )
        )


class LiteEthMACPaddingChecker(Module):
    def __init__(self, dw, packet_min_length):
        self.sink = sink = Sink(eth_phy_description(dw))
        self.source = source = Source(eth_phy_description(dw))

        # # #

        # XXX see if we should drop the packet when
        # payload size < minimum ethernet payload size
        self.comb += Record.connect(sink, source)

