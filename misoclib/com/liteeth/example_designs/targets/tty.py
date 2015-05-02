from misoclib.tools.litescope.common import *
from misoclib.tools.litescope.frontend.la import LiteScopeLA
from misoclib.tools.litescope.core.port import LiteScopeTerm

from misoclib.com.liteeth.common import *

from targets.base import BaseSoC
from misoclib.com.liteeth.frontend.tty import LiteEthTTY


class TTYSoC(BaseSoC):
    default_platform = "kc705"
    def __init__(self, platform):
        BaseSoC.__init__(self, platform,
            mac_address=0x10e2d5000000,
            ip_address="192.168.0.42")
        self.submodules.tty = LiteEthTTY(self.core.udp, convert_ip("192.168.0.14"), 10000)
        self.comb += Record.connect(self.tty.source, self.tty.sink)


class TTYSoCDevel(TTYSoC):
    csr_map = {
        "la":            20
    }
    csr_map.update(TTYSoC.csr_map)
    def __init__(self, platform):
        TTYSoC.__init__(self, platform)
        debug = (
            self.tty.sink.stb,
            self.tty.sink.ack,
            self.tty.sink.data,

            self.tty.source.stb,
            self.tty.source.ack,
            self.tty.source.data
        )
        self.submodules.la = LiteScopeLA(debug, 4096)
        self.la.trigger.add_port(LiteScopeTerm(self.la.dw))

    def do_exit(self, vns):
        self.la.export(vns, "test/la.csv")

default_subtarget = TTYSoC
