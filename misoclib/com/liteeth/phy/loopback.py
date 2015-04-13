from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.generic import *


class LiteEthPHYLoopbackCRG(Module, AutoCSR):
    def __init__(self):
        self._reset = CSRStorage()

        # # #

        self.clock_domains.cd_eth_rx = ClockDomain()
        self.clock_domains.cd_eth_tx = ClockDomain()
        self.comb += [
            self.cd_eth_rx.clk.eq(ClockSignal()),
            self.cd_eth_tx.clk.eq(ClockSignal())
        ]

        reset = self._reset.storage
        self.comb += [
            self.cd_eth_rx.rst.eq(reset),
            self.cd_eth_tx.rst.eq(reset)
        ]


class LiteEthPHYLoopback(Module, AutoCSR):
    def __init__(self):
        self.dw = 8
        self.submodules.crg = LiteEthLoopbackPHYCRG()
        self.sink = sink = Sink(eth_phy_description(8))
        self.source = source = Source(eth_phy_description(8))
        self.comb += Record.connect(self.sink, self.source)
