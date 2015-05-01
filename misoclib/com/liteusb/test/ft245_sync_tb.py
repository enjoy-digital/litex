from migen.fhdl.std import *
from migen.flow.actor import *
from migen.fhdl.specials import *

from migen.sim.generic import run_simulation

from misoclib.com.liteusb.common import *
from misoclib.com.liteusb.phy.ft245 import FT245PHYSynchronous
from misoclib.com.liteusb.test.common import *

# XXX for now use it from liteeth to avoid duplication
from misoclib.com.liteeth.test.common import *

class FT245SynchronousModel(Module, RandRun):
    def __init__(self, rd_data):
        RandRun.__init__(self, 10)
        self.rd_data = [0] + rd_data
        self.rd_idx = 0

        # pads
        self.data = Signal(8)
        self.rxf_n = Signal(reset=1)
        self.txe_n = Signal(reset=1)
        self.rd_n = Signal(reset=1)
        self.wr_n = Signal(reset=1)
        self.oe_n = Signal(reset=1)
        self.siwua = Signal()
        self.pwren_n = Signal(reset=1)

        self.init = True
        self.wr_data = []
        self.wait_wr_n = False
        self.rd_done = 0


        self.data_w = Signal(8)
        self.data_r = Signal(8)

        self.specials += Tristate(self.data, self.data_r, ~self.oe_n, self.data_w)

    def wr_sim(self, selfp):
        if not selfp.wr_n and not selfp.txe_n:
            self.wr_data.append(selfp.data_w)
            self.wait_wr_n = False

        if not self.wait_wr_n:
            if self.run:
                selfp.txe_n = 1
            else:
                if selfp.txe_n:
                    self.wait_wr_n = True
                selfp.txe_n = 0

    def rd_sim(self, selfp):
        rxf_n = selfp.rxf_n
        if self.run:
            if self.rd_idx < len(self.rd_data)-1:
                self.rd_done = selfp.rxf_n
                selfp.rxf_n = 0
            else:
                selfp.rxf_n = self.rd_done
        else:
            selfp.rxf_n = self.rd_done

        if not selfp.rd_n and not selfp.oe_n:
            if self.rd_idx < len(self.rd_data)-1:
                self.rd_idx += not rxf_n
            selfp.data_r = self.rd_data[self.rd_idx]
            self.rd_done = 1

    def do_simulation(self, selfp):
        RandRun.do_simulation(self, selfp)
        if self.init:
            selfp.rxf_n = 0
            self.wr_data = []
            self.init = False
        self.wr_sim(selfp)
        self.rd_sim(selfp)

test_packet = [i%256 for i in range(512)]


class TB(Module):
    def __init__(self):
        self.submodules.model = FT245SynchronousModel(test_packet)
        self.submodules.phy = FT245PHYSynchronous(self.model)

        self.submodules.streamer = PacketStreamer(phy_description(8))
        self.submodules.streamer_randomizer = AckRandomizer(phy_description(8), level=10)

        self.submodules.logger_randomizer = AckRandomizer(phy_description(8), level=10)
        self.submodules.logger = PacketLogger(phy_description(8))

        self.comb += [
            Record.connect(self.streamer.source, self.streamer_randomizer.sink),
            self.phy.sink.stb.eq(self.streamer_randomizer.source.stb),
            self.phy.sink.data.eq(self.streamer_randomizer.source.data),
            self.streamer_randomizer.source.ack.eq(self.phy.sink.ack),

            self.logger_randomizer.sink.stb.eq(self.phy.source.stb),
            self.logger_randomizer.sink.data.eq(self.phy.source.data),
            self.phy.source.ack.eq(self.logger_randomizer.sink.ack),
            Record.connect(self.logger_randomizer.source, self.logger.sink)
        ]

        # Use sys_clk as ftdi_clk in simulation
        self.comb += [
            ClockSignal("ftdi").eq(ClockSignal()),
            ResetSignal("ftdi").eq(ResetSignal())
        ]

    def gen_simulation(self, selfp):
        yield from self.streamer.send(Packet(test_packet))
        for i in range(2000):
            yield
        s, l, e = check(test_packet, self.model.wr_data)
        print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

        s, l, e = check(test_packet, self.logger.packet[1:])
        print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))


def main():
    run_simulation(TB(), ncycles=8000, vcd_name="my.vcd", keep_files=True)

if __name__ == "__main__":
    main()