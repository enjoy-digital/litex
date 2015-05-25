from misoclib.com.liteusb.common import *
from migen.actorlib.structuring import Pack, Unpack
from migen.genlib.misc import WaitTimer

class LiteUSBPacketizer(Module):
    def __init__(self):
        self.sink = sink = Sink(user_description(8))
        self.source = source = Source(phy_description(8))

        # # #

        # Packet description
        #   - preamble : 4 bytes
        #   - dst      : 1 byte
        #   - length   : 4 bytes
        #   - payload
        header = [
            # preamble
            0x5A,
            0xA5,
            0x5A,
            0xA5,
            # dst
            sink.dst,
            # length
            sink.length[24:32],
            sink.length[16:24],
            sink.length[8:16],
            sink.length[0:8],
        ]

        header_unpack = Unpack(len(header), phy_description(8))
        self.submodules += header_unpack

        for i, byte in enumerate(header):
            chunk = getattr(header_unpack.sink.payload, "chunk" + str(i))
            self.comb += chunk.data.eq(byte)

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            If(sink.stb & sink.sop,
                NextState("INSERT_HEADER")
            )
        )

        fsm.act("INSERT_HEADER",
            header_unpack.sink.stb.eq(1),
            source.stb.eq(1),
            source.data.eq(header_unpack.source.data),
            header_unpack.source.ack.eq(source.ack),
            If(header_unpack.sink.ack,
                NextState("COPY")
            )
        )

        fsm.act("COPY",
            source.stb.eq(sink.stb),
            source.data.eq(sink.data),
            sink.ack.eq(source.ack),
            If(source.ack & sink.eop,
                NextState("IDLE")
            )
        )


class LiteUSBDepacketizer(Module):
    def __init__(self, clk_freq, timeout=10):
        self.sink = sink = Sink(phy_description(8))
        self.source = source = Source(user_description(8))

        # # #

        # Packet description
        #   - preamble : 4 bytes
        #   - dst      : 1 byte
        #   - length   : 4 bytes
        #   - payload
        preamble = Array(Signal(8) for i in range(4))

        header = [
            # dst
            source.dst,
            # length
            source.length[24:32],
            source.length[16:24],
            source.length[8:16],
            source.length[0:8],
        ]

        header_pack = InsertReset(Pack(phy_description(8), len(header)))
        self.submodules += header_pack

        for i, byte in enumerate(header):
            chunk = getattr(header_pack.source.payload, "chunk" + str(i))
            self.comb += byte.eq(chunk.data)

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        self.comb += preamble[0].eq(sink.data)
        for i in range(1, 4):
            self.sync += If(sink.stb & sink.ack,
                    preamble[i].eq(preamble[i-1])
            )
        fsm.act("IDLE",
            sink.ack.eq(1),
            If((preamble[3] == 0x5A) &
               (preamble[2] == 0xA5) &
               (preamble[1] == 0x5A) &
               (preamble[0] == 0xA5) &
               sink.stb,
                   NextState("RECEIVE_HEADER")
            ),
            header_pack.source.ack.eq(1),
        )

        self.submodules.timer = WaitTimer(clk_freq*timeout)
        self.comb += self.timer.wait.eq(~fsm.ongoing("IDLE"))

        fsm.act("RECEIVE_HEADER",
            header_pack.sink.stb.eq(sink.stb),
            header_pack.sink.payload.eq(sink.payload),
            If(self.timer.done,
                NextState("IDLE")
            ).Elif(header_pack.source.stb,
                NextState("COPY")
            ).Else(
                sink.ack.eq(1)
            )
        )

        self.comb += header_pack.reset.eq(self.timer.done)

        sop = Signal()
        eop = Signal()
        cnt = Signal(32)

        fsm.act("COPY",
            source.stb.eq(sink.stb),
            source.sop.eq(sop),
            source.eop.eq(eop),
            source.data.eq(sink.data),
            sink.ack.eq(source.ack),
            If((source.stb & source.ack & eop) | self.timer.done,
                NextState("IDLE")
            )
        )

        self.sync += \
            If(fsm.ongoing("IDLE"),
                cnt.eq(0)
            ).Elif(source.stb & source.ack,
                cnt.eq(cnt + 1)
            )
        self.comb += sop.eq(cnt == 0)
        self.comb += eop.eq(cnt == source.length - 1)
