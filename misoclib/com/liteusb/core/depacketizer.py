from migen.fhdl.std import *
from migen.actorlib.structuring import *
from migen.genlib.fsm import FSM, NextState

from misoclib.com.liteusb.common import *

class LiteUSBDepacketizer(Module):
    def __init__(self, timeout=10):
        self.sink = sink = Sink(phy_layout)
        self.source = source = Source(user_layout)

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

        header_pack = InsertReset(Pack(phy_layout, len(header)))
        self.submodules += header_pack

        for i, byte in enumerate(header):
            chunk = getattr(header_pack.source.payload, "chunk" + str(i))
            self.comb += byte.eq(chunk.d)

        fsm = FSM()
        self.submodules += fsm

        self.comb += preamble[0].eq(sink.d)
        for i in range(1, 4):
            self.sync += If(sink.stb & sink.ack,
                    preamble[i].eq(preamble[i-1])
            )
        fsm.act("WAIT_SOP",
            If(    (preamble[3] == 0x5A) &
                (preamble[2] == 0xA5) &
                (preamble[1] == 0x5A) &
                (preamble[0] == 0xA5) &
                sink.stb,
            NextState("RECEIVE_HEADER")
            ),
            sink.ack.eq(1),
            header_pack.source.ack.eq(1),
        )

        self.submodules.timeout = LiteUSBTimeout(60000000, timeout)
        self.comb += self.timeout.clear.eq(fsm.ongoing("WAIT_SOP"))

        fsm.act("RECEIVE_HEADER",
            header_pack.sink.stb.eq(sink.stb),
            header_pack.sink.payload.eq(sink.payload),
            If(self.timeout.done, NextState("WAIT_SOP"))
            .Elif(header_pack.source.stb, NextState("RECEIVE_PAYLOAD"))
            .Else(sink.ack.eq(1))
        )

        self.comb += header_pack.reset.eq(self.timeout.done)

        sop = Signal()
        eop = Signal()
        cnt = Signal(32)

        fsm.act("RECEIVE_PAYLOAD",
            source.stb.eq(sink.stb),
            source.sop.eq(sop),
            source.eop.eq(eop),
            source.d.eq(sink.d),
            sink.ack.eq(source.ack),
            If((eop & sink.stb & source.ack) | self.timeout.done, NextState("WAIT_SOP"))
        )

        self.sync += \
            If(fsm.ongoing("WAIT_SOP"),
                cnt.eq(0)
            ).Elif(source.stb & source.ack,
                cnt.eq(cnt + 1)
            )
        self.comb += sop.eq(cnt == 0)
        self.comb += eop.eq(cnt == source.length - 1)

#
# TB
#
src_data =    [
    0x5A, 0xA5, 0x5A, 0xA5, 0x01, 0x00, 0x00, 0x00, 0x04, 0x00, 0x01, 0x02, 0x03,
    0x5A, 0xA5, 0x5A, 0xA5, 0x12, 0x00, 0x00, 0x00, 0x08, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
]*4

class DepacketizerSourceModel(Module, Source, RandRun):
    def __init__(self, data):
        Source.__init__(self, phy_layout)
        RandRun.__init__(self, 50)
        self.data = data

        self._stb = 0
        self._cnt = 0

    def do_simulation(self, selfp):
        RandRun.do_simulation(self, selfp)

        if self.run and not self._stb:
            self._stb = 1

        if selfp.stb and selfp.ack:
            self._cnt +=1

        selfp.stb =  self._stb
        selfp.d =  self.data[self._cnt]

        if self._cnt  == len(self.data)-1:
            raise StopSimulation


class DepacketizerSinkModel(Module, Sink, RandRun):
    def __init__(self):
        Sink.__init__(self, user_layout, True)
        RandRun.__init__(self, 50)

    def do_simulation(self, selfp):
        RandRun.do_simulation(self, selfp)
        if self.run:
            selfp.ack = 1
        else:
            selfp.ack = 0


class TB(Module):
    def __init__(self):
        self.submodules.source = DepacketizerSourceModel(src_data)
        self.submodules.dut = LiteUSBDepacketizer()
        self.submodules.sink = DepacketizerSinkModel()

        self.comb += [
            self.source.connect(self.dut.sink),
            self.dut.source.connect(self.sink),
        ]

def main():
    from migen.sim.generic import run_simulation
    run_simulation(TB(), ncycles=400, vcd_name="tb_depacketizer.vcd")

if __name__ == "__main__":
    main()
