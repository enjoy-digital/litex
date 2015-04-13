from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.core.link import LiteSATALink

from misoclib.mem.litesata.test.common import *
from misoclib.mem.litesata.test.hdd import *


class LinkStreamer(PacketStreamer):
    def __init__(self):
        PacketStreamer.__init__(self, link_description(32), LinkTXPacket)


class LinkLogger(PacketLogger):
    def __init__(self):
        PacketLogger.__init__(self, link_description(32), LinkRXPacket)


class TB(Module):
    def __init__(self):
        self.submodules.hdd = HDD(
                link_debug=False, link_random_level=50,
                transport_debug=False, transport_loopback=True)
        self.submodules.link = InsertReset(LiteSATALink(self.hdd.phy, buffer_depth=512))

        self.submodules.streamer = LinkStreamer()
        self.submodules.streamer_randomizer = Randomizer(link_description(32), level=50)

        self.submodules.logger_randomizer = Randomizer(link_description(32), level=50)
        self.submodules.logger = LinkLogger()

        self.submodules.pipeline = Pipeline(
            self.streamer,
            self.streamer_randomizer,
            self.link,
            self.logger_randomizer,
            self.logger
        )

    def gen_simulation(self, selfp):
        for i in range(8):
            streamer_packet = LinkTXPacket([i for i in range(64)])
            yield from self.streamer.send(streamer_packet)
            yield from self.logger.receive()

            # check results
            s, l, e = check(streamer_packet, self.logger.packet)
            print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))


if __name__ == "__main__":
    run_simulation(TB(), ncycles=2048, vcd_name="my.vcd", keep_files=True)
