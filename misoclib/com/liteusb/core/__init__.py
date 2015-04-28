from misoclib.com.liteusb.common import *
from misoclib.com.liteusb.core.packet import LiteUSBPacketizer, LiteUSBDepacketizer
from misoclib.com.liteusb.core.crc import LiteUSBCRC32Inserter, LiteUSBCRC32Checker
from misoclib.com.liteusb.core.crossbar import LiteUSBCrossbar

# XXX Header should be protected by CRC

class LiteUSBCore(Module):
    def __init__(self, phy):
        # depacketizer / packetizer
        self.submodules.depacketizer = LiteUSBDepacketizer()
        self.submodules.packetizer = LiteUSBPacketizer()
        self.comb += [
            Record.connect(phy.source, self.depacketizer.sink),
            Record.connect(self.packetizer.source, phy.sink)
        ]

        # crc checker / inserter
        self.submodules.crc_rx = LiteUSBCRC32Checker()
        self.submodules.crc_tx = LiteUSBCRC32Inserter()
        self.comb += [
            Record.connect(self.depacketizer.source, self.crc_rx.sink),
            Record.connect(self.crc_tx.source, self.packetizer.sink)
        ]

       # crossbar
        self.submodules.crossbar = LiteUSBCrossbar()
        self.comb += [
            Record.connect(self.crossbar.master.source, self.crc_tx.sink),
            Record.connect(self.crc_rx.source, self.crossbar.master.sink)
        ]
