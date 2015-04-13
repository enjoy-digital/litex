from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.core import LiteSATACore

from misoclib.mem.litesata.test.hdd import *
from misoclib.mem.litesata.test.common import *


class CommandTXPacket(list):
    def __init__(self, write=0, read=0, sector=0, count=0, data=[]):
        self.ongoing = False
        self.done = False
        self.write = write
        self.read = read
        self.sector = sector
        self.count = count
        for d in data:
            self.append(d)


class CommandStreamer(PacketStreamer):
    def __init__(self):
        PacketStreamer.__init__(self, command_tx_description(32), CommandTXPacket)

    def do_simulation(self, selfp):
        PacketStreamer.do_simulation(self, selfp)
        selfp.source.write = self.packet.write
        selfp.source.read = self.packet.read
        selfp.source.sector = self.packet.sector
        selfp.source.count = self.packet.count


class CommandRXPacket(list):
    def __init__(self):
        self.ongoing = False
        self.done = False
        self.write = 0
        self.read = 0
        self.failed = 0


class CommandLogger(PacketLogger):
    def __init__(self):
        PacketLogger.__init__(self, command_rx_description(32), CommandRXPacket)

    def do_simulation(self, selfp):
        selfp.sink.ack = 1
        if selfp.sink.stb == 1 and selfp.sink.sop == 1:
            self.packet = CommandRXPacket()
            self.packet.write = selfp.sink.write
            self.packet.read = selfp.sink.read
            self.packet.failed = selfp.sink.failed
            self.packet.append(selfp.sink.data)
        elif selfp.sink.stb:
            self.packet.append(selfp.sink.data)
        if selfp.sink.stb == 1 and selfp.sink.eop == 1:
            self.packet.done = True


class TB(Module):
    def __init__(self):
        self.submodules.hdd = HDD(
                link_debug=False, link_random_level=50,
                transport_debug=False, transport_loopback=False,
                hdd_debug=True)
        self.submodules.core = LiteSATACore(self.hdd.phy, buffer_depth=512)

        self.submodules.streamer = CommandStreamer()
        self.submodules.streamer_randomizer = Randomizer(command_tx_description(32), level=50)

        self.submodules.logger = CommandLogger()
        self.submodules.logger_randomizer = Randomizer(command_rx_description(32), level=50)

        self.submodules.pipeline = Pipeline(
            self.streamer,
            self.streamer_randomizer,
            self.core,
            self.logger_randomizer,
            self.logger
        )

    def gen_simulation(self, selfp):
        hdd = self.hdd
        hdd.malloc(0, 64)
        write_data = [i for i in range(sectors2dwords(2))]
        write_len = dwords2sectors(len(write_data))
        write_packet = CommandTXPacket(write=1, sector=2, count=write_len, data=write_data)
        yield from self.streamer.send(write_packet)
        yield from self.logger.receive()
        read_packet = CommandTXPacket(read=1, sector=2, count=write_len)
        yield from self.streamer.send(read_packet)
        yield from self.logger.receive()
        read_data = self.logger.packet

        # check results
        s, l, e = check(write_data, read_data)
        print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
    run_simulation(TB(), ncycles=2048, vcd_name="my.vcd", keep_files=True)
