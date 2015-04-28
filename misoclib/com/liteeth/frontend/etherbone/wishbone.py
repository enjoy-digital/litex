from misoclib.com.liteeth.common import *
from migen.bus import wishbone


class LiteEthEtherboneWishboneMaster(Module):
    def __init__(self):
        self.sink = sink = Sink(eth_etherbone_mmap_description(32))
        self.source = source = Source(eth_etherbone_mmap_description(32))
        self.bus = bus = wishbone.Interface()

        # # #

        self.submodules.data = data = FlipFlop(32)
        self.comb += data.d.eq(bus.dat_r)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            sink.ack.eq(1),
            If(sink.stb & sink.sop,
                sink.ack.eq(0),
                If(sink.we,
                    NextState("WRITE_DATA")
                ).Else(
                    NextState("READ_DATA")
                )
            )
        )
        fsm.act("WRITE_DATA",
            bus.adr.eq(sink.addr),
            bus.dat_w.eq(sink.data),
            bus.sel.eq(sink.be),
            bus.stb.eq(sink.stb),
            bus.we.eq(1),
            bus.cyc.eq(1),
            If(bus.stb & bus.ack,
                sink.ack.eq(1),
                If(sink.eop,
                    NextState("IDLE")
                )
            )
        )
        fsm.act("READ_DATA",
            bus.adr.eq(sink.addr),
            bus.sel.eq(sink.be),
            bus.stb.eq(sink.stb),
            bus.cyc.eq(1),
            If(bus.stb & bus.ack,
                data.ce.eq(1),
                NextState("SEND_DATA")
            )
        )
        fsm.act("SEND_DATA",
            source.stb.eq(sink.stb),
            source.sop.eq(sink.sop),
            source.eop.eq(sink.eop),
            source.base_addr.eq(sink.base_addr),
            source.addr.eq(sink.addr),
            source.count.eq(sink.count),
            source.be.eq(sink.be),
            source.we.eq(1),
            source.data.eq(data.q),
            If(source.stb & source.ack,
                sink.ack.eq(1),
                If(source.eop,
                    NextState("IDLE")
                ).Else(
                    NextState("READ_DATA")
                )
            )
        )
