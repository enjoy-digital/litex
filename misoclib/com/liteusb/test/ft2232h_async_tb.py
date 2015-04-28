from migen.fhdl.std import *
from migen.flow.actor import *
from migen.fhdl.specials import *

from migen.sim.generic import run_simulation

from misoclib.com.liteusb.common import *
from misoclib.com.liteusb.phy.ft2232h import FT2232HPHYAsynchronous
from misoclib.com.liteusb.test.common import *

# XXX for now use it from liteeth to avoid duplication
from misoclib.com.liteeth.test.common import *

class FT2232HAsynchronousModel(Module, RandRun):
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

        self.init = True
        self.wr_data = []
        self.wait_wr_n = False
        self.rd_done = 0


        self.data_w = Signal(8)
        self.data_r = Signal(8)

        self.specials += Tristate(self.data, self.data_r, ~self.rd_n, self.data_w)

        self.last_wr_n = 1
        self.last_rd_n = 1

        self.wr_delay = 0
        self.rd_delay = 0

    def wr_sim(self, selfp):
        if self.wr_delay:
            selfp.txe_n = 1
            self.wr_delay = self.wr_delay - 1
        else:
            if (not selfp.wr_n and self.last_wr_n) and not selfp.txe_n:
                self.wr_data.append(selfp.data_w)
                self.wr_delay = 20 # XXX FIXME
            self.last_wr_n = selfp.wr_n

            if self.run:
                selfp.txe_n = 0

    def rd_sim(self, selfp):
        if self.rd_delay:
            selfp.rxf_n = 1
            self.rd_delay = self.rd_delay - 1
        else:
            rxf_n = selfp.rxf_n
            if self.run:
                if self.rd_idx < len(self.rd_data)-1:
                    self.rd_done = selfp.rxf_n
                    selfp.rxf_n = 0
                else:
                    selfp.rxf_n = self.rd_done
            else:
                selfp.rxf_n = self.rd_done

            if not selfp.rd_n and self.last_rd_n:
                if self.rd_idx < len(self.rd_data)-1:
                    self.rd_idx += not rxf_n
                selfp.data_r = self.rd_data[self.rd_idx]
                self.rd_done = 1
            if selfp.rd_n and not self.last_rd_n:
                self.rd_delay = 4 # XXX FIXME

        self.last_rd_n = selfp.rd_n

    def do_simulation(self, selfp):
        RandRun.do_simulation(self, selfp)
        if self.init:
            selfp.rxf_n = 0
            self.wr_data = []
            self.init = False
        self.wr_sim(selfp)
        self.rd_sim(selfp)

test_packet = [i%256 for i in range(128)]


class TB(Module):
    def __init__(self):
        self.submodules.model = FT2232HAsynchronousModel(test_packet)
        self.submodules.phy = FT2232HPHYAsynchronous(self.model, 50000000)

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

    def gen_simulation(self, selfp):
        yield from self.streamer.send(Packet(test_packet))
        for i in range(4000):
            yield
        s, l, e = check(test_packet, self.model.wr_data)
        print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

        s, l, e = check(test_packet, self.logger.packet)
        print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))


def main():
    run_simulation(TB(), ncycles=8000, vcd_name="my.vcd", keep_files=True)

if __name__ == "__main__":
    main()