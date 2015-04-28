from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.crossbar import LiteEthCrossbar


class LiteEthIPV4MasterPort:
    def __init__(self, dw):
        self.dw = dw
        self.source = Source(eth_ipv4_user_description(dw))
        self.sink = Sink(eth_ipv4_user_description(dw))


class LiteEthIPV4SlavePort:
    def __init__(self, dw):
        self.dw = dw
        self.sink = Sink(eth_ipv4_user_description(dw))
        self.source = Source(eth_ipv4_user_description(dw))


class LiteEthIPV4UserPort(LiteEthIPV4SlavePort):
    def __init__(self, dw):
        LiteEthIPV4SlavePort.__init__(self, dw)


class LiteEthIPV4Crossbar(LiteEthCrossbar):
    def __init__(self):
        LiteEthCrossbar.__init__(self, LiteEthIPV4MasterPort, "protocol")

    def get_port(self, protocol):
        if protocol in self.users.keys():
            raise ValueError("Protocol {0:#x} already assigned".format(protocol))
        port = LiteEthIPV4UserPort(8)
        self.users[protocol] = port
        return port
