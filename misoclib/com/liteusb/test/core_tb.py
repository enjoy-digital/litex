import binascii

from migen.fhdl.std import *
from migen.flow.actor import *
from migen.fhdl.specials import *

from migen.sim.generic import run_simulation

from misoclib.com.liteusb.common import *
from misoclib.com.liteusb.core import LiteUSBCore
from misoclib.com.liteusb.test.common import *

# XXX for now use it from liteeth to avoid duplication
from misoclib.com.liteeth.test.common import *

def crc32(l):
    crc = []
    crc_bytes = split_bytes(binascii.crc32(bytes(l)), 4, "little")
    for byte in crc_bytes:
        crc.append(int(byte))
    return crc


class USBPacket(Packet):
    def __init__(self, init=[]):
        Packet.__init__(self, init)
        self.crc_error = False

    def check_remove_crc(self):
        if comp(self[-4:], crc32(self[:-4])):
            for i in range(4):
                self.pop()
            return False
        else:
            return True

    def decode_remove_header(self):
        header = []
        for byte in self[:packet_header.length]:
            header.append(self.pop(0))
        for k, v in sorted(packet_header.fields.items()):
            setattr(self, k, get_field_data(v, header))

    def decode(self):
        # XXX Header should be protected by CRC
        self.decode_remove_header()
        self.crc_error = self.check_remove_crc()
        if self.crc_error:
            raise ValueError  # XXX handle this properly

    def encode_header(self):
        header = 0
        for k, v in sorted(packet_header.fields.items()):
            value = merge_bytes(split_bytes(getattr(self, k),
                                            math.ceil(v.width/8)),
                                            "little")
            header += (value << v.offset+(v.byte*8))
        for d in split_bytes(header, packet_header.length):
            self.insert(0, d)

    def insert_crc(self):
        for d in crc32(self):
            self.append(d)

    def encode(self):
        # XXX Header should be protected by CRC
        self.insert_crc()
        self.encode_header()

    def __repr__(self):
        r = "--------\n"
        for k in sorted(packet_header.fields.keys()):
            r += k + " : 0x{:0x}\n".format(getattr(self, k))
        r += "payload: "
        for d in self:
            r += "{:02x}".format(d)
        return r


class PHYModel(Module):
    def __init__(self):
        self.sink = Sink(phy_description(8))
        self.source = Source(phy_description(8))

class TB(Module):
    def __init__(self):
        self.submodules.phy = PHYModel()
        self.submodules.core = LiteUSBCore(self.phy)

        self.submodules.phy_streamer = PacketStreamer(phy_description(8))
        self.submodules.phy_streamer_randomizer = AckRandomizer(phy_description(8), level=0)

        self.submodules.phy_logger_randomizer = AckRandomizer(phy_description(8), level=0)
        self.submodules.phy_logger = PacketLogger(phy_description(8))

        self.submodules.core_streamer = PacketStreamer(user_description(8))
        self.submodules.core_streamer_randomizer = AckRandomizer(user_description(8), level=10)

        self.submodules.core_logger = PacketLogger(user_description(8))
        self.submodules.core_logger_randomizer = AckRandomizer(user_description(8), level=10)


        user_port = self.core.crossbar.get_port(0x12)


        self.comb += [
            Record.connect(self.phy_streamer.source, self.phy_streamer_randomizer.sink),
            Record.connect(self.phy_streamer_randomizer.source, self.phy.source),

            Record.connect(self.core_streamer.source, self.core_streamer_randomizer.sink),
            Record.connect(self.core_streamer_randomizer.source, user_port.sink),

            Record.connect(user_port.source, self.core_logger_randomizer.sink),
            Record.connect(self.core_logger_randomizer.source, self.core_logger.sink),

            Record.connect(self.phy.sink, self.phy_logger_randomizer.sink),
            Record.connect(self.phy_logger_randomizer.source, self.phy_logger.sink)
        ]

    def gen_simulation(self, selfp):
        packet = USBPacket([i for i in range(128)])
        packet.preamble = 0x5AA55AA5
        packet.dst = 0x12
        packet.length = 128 + 4
        packet.encode()
        yield from self.phy_streamer.send(packet)
        for i in range(32):
            yield
        print(self.core_logger.packet)

        selfp.core_streamer.source.dst = 0x12
        selfp.core_streamer.source.length = 128 + 4
        packet = Packet([i for i in range(128)])
        yield from self.core_streamer.send(packet)
        for i in range(32):
            yield
        for d in self.phy_logger.packet:
            print("%02x" %d, end="")
        print("")
        packet = USBPacket(self.phy_logger.packet)
        packet.decode()
        print(packet)

def main():
    run_simulation(TB(), ncycles=2000, vcd_name="my.vcd", keep_files=True)

if __name__ == "__main__":
    main()