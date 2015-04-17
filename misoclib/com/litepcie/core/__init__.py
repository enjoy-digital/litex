from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.record import *

from misoclib.com.litepcie.core.packet.depacketizer import Depacketizer
from misoclib.com.litepcie.core.packet.packetizer import Packetizer
from misoclib.com.litepcie.core.switch.crossbar import Crossbar


class Endpoint(Module):
    def __init__(self, phy, max_pending_requests=4, with_reordering=False):
        self.phy = phy
        self.max_pending_requests = max_pending_requests

        # # #

        # TLP Packetizer / Depacketizer
        depacketizer = Depacketizer(phy.dw, phy.bar0_mask)
        packetizer = Packetizer(phy.dw)
        self.submodules += depacketizer, packetizer
        self.comb += [
            phy.source.connect(depacketizer.sink),
            packetizer.source.connect(phy.sink)
        ]

        # Crossbar
        self.crossbar = crossbar = Crossbar(phy.dw, max_pending_requests, with_reordering)
        self.submodules += crossbar

        # (Slave) HOST initiates the transactions
        self.comb += [
            Record.connect(depacketizer.req_source, crossbar.phy_slave.sink),
            Record.connect(crossbar.phy_slave.source, packetizer.cmp_sink)
        ]

        # (Master) FPGA initiates the transactions
        self.comb += [
            Record.connect(crossbar.phy_master.source, packetizer.req_sink),
            Record.connect(depacketizer.cmp_source, crossbar.phy_master.sink)
        ]
