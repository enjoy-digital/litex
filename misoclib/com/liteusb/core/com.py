from migen.fhdl.std import *
from migen.flow.actor import *

from misoclib.com.liteusb.common import *
from misoclib.com.liteusb.frontend.crossbar import LiteUSBCrossbar
from misoclib.com.liteusb.core.packetizer import LiteUSBPacketizer
from misoclib.com.liteusb.core.depacketizer import LiteUSBDepacketizer

class LiteUSBCom(Module):
    def __init__(self, phy, *ports):
        # crossbar
        self.submodules.crossbar = LiteUSBCrossbar(list(ports))

        # packetizer / depacketizer
        self.submodules.packetizer = LiteUSBPacketizer()
        self.submodules.depacketizer = LiteUSBDepacketizer()
        self.comb += [
            self.crossbar.slave.source.connect(self.packetizer.sink),
            self.depacketizer.source.connect(self.crossbar.slave.sink)
        ]

        # phy
        self.comb += [
            self.packetizer.source.connect(phy.sink),
            phy.source.connect(self.depacketizer.sink)
        ]
