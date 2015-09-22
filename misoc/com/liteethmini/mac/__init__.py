from misoc.com.liteethmini.common import *
from misoc.com.liteethmini.mac.core import LiteEthMACCore
from misoc.com.liteethmini.mac.frontend.wishbone import LiteEthMACWishboneInterface


class LiteEthMAC(Module, AutoCSR):
    def __init__(self, phy, dw,
                 interface="wishbone",
                 endianness="big",
                 with_preamble_crc=True):
        self.submodules.core = LiteEthMACCore(phy, dw, endianness, with_preamble_crc)
        self.csrs = []
        if interface == "wishbone":
            self.submodules.interface = LiteEthMACWishboneInterface(dw, 2, 2)
            self.comb += Port.connect(self.interface, self.core)
            self.ev, self.bus = self.interface.sram.ev, self.interface.bus
            self.csrs = self.interface.get_csrs() + self.core.get_csrs()
        else:
            raise NotImplementedError

    def get_csrs(self):
        return self.csrs
