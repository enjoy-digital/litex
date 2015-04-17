from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState
from migen.bus import wishbone

from misoclib.com.litepcie.common import *


class WishboneBridge(Module):
    def __init__(self, endpoint, address_decoder):
        self.wishbone = wishbone.Interface()

        # # #

        port = endpoint.crossbar.get_slave_port(address_decoder)
        self.submodules.fsm = fsm = FSM()

        fsm.act("IDLE",
            If(port.sink.stb & port.sink.sop,
                If(port.sink.we,
                    NextState("WRITE"),
                ).Else(
                    NextState("READ")
                )
            ).Else(
                port.sink.ack.eq(port.sink.stb)
            )
        )
        fsm.act("WRITE",
            self.wishbone.adr.eq(port.sink.adr[2:]),
            self.wishbone.dat_w.eq(port.sink.dat[:32]),
            self.wishbone.sel.eq(0xf),
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(1),
            self.wishbone.cyc.eq(1),
            If(self.wishbone.ack,
                port.sink.ack.eq(1),
                NextState("IDLE")
            )
        )
        fsm.act("READ",
            self.wishbone.adr.eq(port.sink.adr[2:]),
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(0),
            self.wishbone.cyc.eq(1),
            If(self.wishbone.ack,
                NextState("COMPLETION")
            )
        )
        self.sync += \
            If(self.wishbone.stb & self.wishbone.ack,
                port.source.dat.eq(self.wishbone.dat_r),
            )
        fsm.act("COMPLETION",
            port.source.stb.eq(1),
            port.source.sop.eq(1),
            port.source.eop.eq(1),
            port.source.len.eq(1),
            port.source.err.eq(0),
            port.source.tag.eq(port.sink.tag),
            port.source.adr.eq(port.sink.adr),
            port.source.cmp_id.eq(endpoint.phy.id),
            port.source.req_id.eq(port.sink.req_id),
            If(port.source.ack,
                port.sink.ack.eq(1),
                NextState("IDLE")
            )
        )
