from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core.mac.common import *
from misoclib.com.liteeth.core.mac.core import LiteEthMACCore
from misoclib.com.liteeth.core.mac.frontend.wishbone import LiteEthMACWishboneInterface


class LiteEthMAC(Module, AutoCSR):
    def __init__(self, phy, dw,
                 interface="crossbar",
                 endianness="big",
                 with_preamble_crc=True):
        self.submodules.core = LiteEthMACCore(phy, dw, endianness, with_preamble_crc)
        self.csrs = []
        if interface == "crossbar":
            self.submodules.crossbar = LiteEthMACCrossbar()
            self.submodules.packetizer = LiteEthMACPacketizer()
            self.submodules.depacketizer = LiteEthMACDepacketizer()
            self.comb += [
                Record.connect(self.crossbar.master.source, self.packetizer.sink),
                Record.connect(self.packetizer.source, self.core.sink),
                Record.connect(self.core.source, self.depacketizer.sink),
                Record.connect(self.depacketizer.source, self.crossbar.master.sink)
            ]
        elif interface == "wishbone":
            self.submodules.interface = LiteEthMACWishboneInterface(dw, 2, 2)
            self.comb += Port.connect(self.interface, self.core)
            self.ev, self.bus = self.interface.sram.ev, self.interface.bus
            self.csrs = self.interface.get_csrs() + self.core.get_csrs()
        else:
            raise NotImplementedError

    def get_csrs(self):
        return self.csrs
