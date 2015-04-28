import os

from misoclib.com.liteeth.common import *


class LiteEthPHYSimCRG(Module, AutoCSR):
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


class LiteEthPHYSim(Module, AutoCSR):
    def __init__(self, pads, tap="tap0", ip_address="192.168.0.14"):
        self.dw = 8
        self.submodules.crg = LiteEthPHYSimCRG()
        self.sink = sink = Sink(eth_phy_description(8))
        self.source = source = Source(eth_phy_description(8))
        self.tap = tap
        self.ip_address = ip_address

        self.comb += [
            pads.source_stb.eq(self.sink.stb),
            pads.source_data.eq(self.sink.data),
            self.sink.ack.eq(1)
        ]

        self.sync += [
            self.source.stb.eq(pads.sink_stb),
            self.source.sop.eq(pads.sink_stb & ~self.source.stb),
            self.source.data.eq(pads.sink_data),
        ]
        self.comb += [
            self.source.eop.eq(~pads.sink_stb & self.source.stb),
        ]

        # XXX avoid use of os.system
        os.system("openvpn --mktun --dev {}".format(self.tap))
        os.system("ifconfig {} {} up".format(self.tap, self.ip_address))
        os.system("mknod /dev/net/{} c 10 200".format(self.tap))

    def do_exit(self, *args, **kwargs):
        # XXX avoid use of os.system
        os.system("rm -f /dev/net/{}".format(self.tap))
        os.system("openvpn --rmtun --dev {}".format(self.tap))
