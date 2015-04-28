from misoclib.com.liteeth.common import *


class LiteEthMACTXLastBE(Module):
    def __init__(self, dw):
        self.sink = sink = Sink(eth_phy_description(dw))
        self.source = source = Source(eth_phy_description(dw))

        # # #

        ongoing = Signal()
        self.sync += \
            If(sink.stb & sink.ack,
                If(sink.sop,
                    ongoing.eq(1)
                ).Elif(sink.last_be,
                    ongoing.eq(0)
                )
            )
        self.comb += [
            source.stb.eq(sink.stb & (sink.sop | ongoing)),
            source.sop.eq(sink.sop),
            source.eop.eq(sink.last_be),
            source.data.eq(sink.data),
            sink.ack.eq(source.ack)
        ]


class LiteEthMACRXLastBE(Module):
    def __init__(self, dw):
        self.sink = sink = Sink(eth_phy_description(dw))
        self.source = source = Source(eth_phy_description(dw))

        # # #

        self.comb += [
            source.stb.eq(sink.stb),
            source.sop.eq(sink.sop),
            source.eop.eq(sink.eop),
            source.data.eq(sink.data),
            source.last_be.eq(sink.eop),
            sink.ack.eq(source.ack)
        ]
