from misoclib.com.liteeth.common import *


class LiteEthEtherboneProbe(Module):
    def __init__(self):
        self.sink = sink = Sink(eth_etherbone_packet_user_description(32))
        self.source = source = Source(eth_etherbone_packet_user_description(32))

        # # #

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            sink.ack.eq(1),
            If(sink.stb & sink.sop,
                sink.ack.eq(0),
                NextState("PROBE_RESPONSE")
            )
        )
        fsm.act("PROBE_RESPONSE",
            Record.connect(sink, source),
            source.pf.eq(0),
            source.pr.eq(1),
            If(source.stb & source.eop & source.ack,
                NextState("IDLE")
            )
        )
