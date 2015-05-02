from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.crossbar import LiteEthCrossbar


class LiteEthMACDepacketizer(Depacketizer):
    def __init__(self):
        Depacketizer.__init__(self,
            eth_phy_description(8),
            eth_mac_description(8),
            mac_header)


class LiteEthMACPacketizer(Packetizer):
    def __init__(self):
        Packetizer.__init__(self,
            eth_mac_description(8),
            eth_phy_description(8),
            mac_header)


class LiteEthMACMasterPort:
    def __init__(self, dw):
        self.source = Source(eth_mac_description(dw))
        self.sink = Sink(eth_mac_description(dw))


class LiteEthMACSlavePort:
    def __init__(self, dw):
        self.sink = Sink(eth_mac_description(dw))
        self.source = Source(eth_mac_description(dw))


class LiteEthMACUserPort(LiteEthMACSlavePort):
    def __init__(self, dw):
        LiteEthMACSlavePort.__init__(self, dw)


class LiteEthMACCrossbar(LiteEthCrossbar):
    def __init__(self):
        LiteEthCrossbar.__init__(self, LiteEthMACMasterPort, "ethernet_type")

    def get_port(self, ethernet_type):
        port = LiteEthMACUserPort(8)
        if ethernet_type in self.users.keys():
            raise ValueError("Ethernet type {0:#x} already assigned".format(ethernet_type))
        self.users[ethernet_type] = port
        return port
