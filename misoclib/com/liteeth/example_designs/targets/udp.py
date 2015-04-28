from misoclib.tools.litescope.common import *
from misoclib.tools.litescope.frontend.la import LiteScopeLA
from misoclib.tools.litescope.core.port import LiteScopeTerm

from misoclib.com.liteeth.common import *

from targets.base import BaseSoC


class UDPSoC(BaseSoC):
    default_platform = "kc705"
    def __init__(self, platform):
        BaseSoC.__init__(self, platform,
            mac_address=0x10e2d5000000,
            ip_address="192.168.0.42")

        # add udp loopback on port 6000 with dw=8
        self.add_udp_loopback(6000, 8,  8192, "loopback_8")
        # add udp loopback on port 8000 with dw=32
        self.add_udp_loopback(8000, 32, 8192, "loopback_32")

    def add_udp_loopback(self, port, dw, depth, name=None):
        port = self.core.udp.crossbar.get_port(port, dw)
        buf = Buffer(eth_udp_user_description(dw), depth//(dw//8), 8)
        if name is None:
            self.submodules += buf
        else:
            setattr(self.submodules, name, buf)
        self.comb += Port.connect(port, buf)


class UDPSoCDevel(UDPSoC):
    csr_map = {
        "la":            20
    }
    csr_map.update(UDPSoC.csr_map)
    def __init__(self, platform):
        UDPSoC.__init__(self, platform)
        debug = (
            self.loopback_8.sink.stb,
            self.loopback_8.sink.sop,
            self.loopback_8.sink.eop,
            self.loopback_8.sink.ack,
            self.loopback_8.sink.data,

            self.loopback_8.source.stb,
            self.loopback_8.source.sop,
            self.loopback_8.source.eop,
            self.loopback_8.source.ack,
            self.loopback_8.source.data,

            self.loopback_32.sink.stb,
            self.loopback_32.sink.sop,
            self.loopback_32.sink.eop,
            self.loopback_32.sink.ack,
            self.loopback_32.sink.data,

            self.loopback_32.source.stb,
            self.loopback_32.source.sop,
            self.loopback_32.source.eop,
            self.loopback_32.source.ack,
            self.loopback_32.source.data
        )
        self.submodules.la = LiteScopeLA(debug, 4096)
        self.la.trigger.add_port(LiteScopeTerm(self.la.dw))

    def do_exit(self, vns):
        self.la.export(vns, "test/la.csv")

default_subtarget = UDPSoC
