from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.generic import *


class LiteEthPacketizer(Module):
    def __init__(self, sink_description, source_description, header):
        self.sink = sink = Sink(sink_description)
        self.source = source = Source(source_description)
        self.header = Signal(header.length*8)

        # # #

        dw = flen(self.sink.data)

        header_reg = Signal(header.length*8)
        header_words = (header.length*8)//dw
        load = Signal()
        shift = Signal()
        counter = Counter(max=max(header_words, 2))
        self.submodules += counter

        self.comb += header.encode(sink, self.header)
        if header_words == 1:
            self.sync += [
                If(load,
                    header_reg.eq(self.header)
                )
            ]
        else:
            self.sync += [
                If(load,
                    header_reg.eq(self.header)
                ).Elif(shift,
                    header_reg.eq(Cat(header_reg[dw:], Signal(dw)))
                )
            ]

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        if header_words == 1:
            idle_next_state = "COPY"
        else:
            idle_next_state = "SEND_HEADER"

        fsm.act("IDLE",
            sink.ack.eq(1),
            counter.reset.eq(1),
            If(sink.stb & sink.sop,
                sink.ack.eq(0),
                source.stb.eq(1),
                source.sop.eq(1),
                source.eop.eq(0),
                source.data.eq(self.header[:dw]),
                If(source.stb & source.ack,
                    load.eq(1),
                    NextState(idle_next_state)
                )
            )
        )
        if header_words != 1:
            fsm.act("SEND_HEADER",
                source.stb.eq(1),
                source.sop.eq(0),
                source.eop.eq(0),
                source.data.eq(header_reg[dw:2*dw]),
                If(source.stb & source.ack,
                    shift.eq(1),
                    counter.ce.eq(1),
                    If(counter.value == header_words-2,
                        NextState("COPY")
                    )
                )
            )
        fsm.act("COPY",
            source.stb.eq(sink.stb),
            source.sop.eq(0),
            source.eop.eq(sink.eop),
            source.data.eq(sink.data),
            source.error.eq(sink.error),
            If(source.stb & source.ack,
                sink.ack.eq(1),
                If(source.eop,
                    NextState("IDLE")
                )
            )
        )
