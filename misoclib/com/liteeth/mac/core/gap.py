from misoclib.com.liteeth.common import *

class LiteEthMACGap(Module):
    def __init__(self, dw, ack_on_gap=False):
        self.sink = sink = Sink(eth_phy_description(dw))
        self.source = source = Source(eth_phy_description(dw))

        # # #

        gap = math.ceil(eth_interpacket_gap/(dw//8))
        self.submodules.counter = counter = Counter(max=gap)

        self.submodules.fsm = fsm = FSM(reset_state="COPY")
        fsm.act("COPY",
            counter.reset.eq(1),
            Record.connect(sink, source),
            If(sink.stb & sink.eop & sink.ack,
                NextState("GAP")
            )
        )
        fsm.act("GAP",
            counter.ce.eq(1),
            sink.ack.eq(int(ack_on_gap)),
            If(counter.value == (gap-1),
                NextState("COPY")
            )
        )
