from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.test.common import *


def print_phy(s):
    print_with_prefix(s, "[PHY]")


# PHY model
class PHYSource(PacketStreamer):
    def __init__(self, dw):
        PacketStreamer.__init__(self, eth_phy_description(dw))


class PHYSink(PacketLogger):
    def __init__(self, dw):
        PacketLogger.__init__(self, eth_phy_description(dw))


class PHY(Module):
    def __init__(self, dw, debug=False):
        self.dw = dw
        self.debug = debug

        self.submodules.phy_source = PHYSource(dw)
        self.submodules.phy_sink = PHYSink(dw)

        self.source = self.phy_source.source
        self.sink = self.phy_sink.sink

        self.mac_callback = None

    def set_mac_callback(self, callback):
        self.mac_callback = callback

    def send(self, datas):
        packet = Packet(datas)
        if self.debug:
            r = ">>>>>>>>\n"
            r += "length " + str(len(datas)) + "\n"
            for d in datas:
                r += "{:02x}".format(d)
            print_phy(r)
        self.phy_source.send(packet)

    def receive(self):
        yield from self.phy_sink.receive()
        if self.debug:
            r = "<<<<<<<<\n"
            r += "length " + str(len(self.phy_sink.packet)) + "\n"
            for d in self.phy_sink.packet:
                r += "{:02x}".format(d)
            print_phy(r)
        self.packet = self.phy_sink.packet

    def gen_simulation(self, selfp):
        while True:
            yield from self.receive()
            if self.mac_callback is not None:
                self.mac_callback(self.packet)
