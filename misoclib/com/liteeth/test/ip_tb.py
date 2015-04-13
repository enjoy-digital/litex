from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core import LiteEthIPCore

from misoclib.com.liteeth.test.common import *
from misoclib.com.liteeth.test.model import phy, mac, arp, ip

ip_address = 0x12345678
mac_address = 0x12345678abcd


class TB(Module):
    def __init__(self):
        self.submodules.phy_model = phy.PHY(8, debug=False)
        self.submodules.mac_model = mac.MAC(self.phy_model, debug=False, loopback=False)
        self.submodules.arp_model = arp.ARP(self.mac_model, mac_address, ip_address, debug=False)
        self.submodules.ip_model = ip.IP(self.mac_model, mac_address, ip_address, debug=False, loopback=True)

        self.submodules.ip = LiteEthIPCore(self.phy_model, mac_address, ip_address, 100000)
        self.ip_port = self.ip.ip.crossbar.get_port(udp_protocol)

        # use sys_clk for each clock_domain
        self.clock_domains.cd_eth_rx = ClockDomain()
        self.clock_domains.cd_eth_tx = ClockDomain()
        self.comb += [
            self.cd_eth_rx.clk.eq(ClockSignal()),
            self.cd_eth_rx.rst.eq(ResetSignal()),
            self.cd_eth_tx.clk.eq(ClockSignal()),
            self.cd_eth_tx.rst.eq(ResetSignal()),
        ]

    def gen_simulation(self, selfp):
        selfp.cd_eth_rx.rst = 1
        selfp.cd_eth_tx.rst = 1
        yield
        selfp.cd_eth_rx.rst = 0
        selfp.cd_eth_tx.rst = 0

        for i in range(100):
            yield

        while True:
            selfp.ip_port.sink.stb = 1
            selfp.ip_port.sink.sop = 1
            selfp.ip_port.sink.eop = 1
            selfp.ip_port.sink.ip_address = 0x12345678
            selfp.ip_port.sink.protocol = udp_protocol

            selfp.ip_port.source.ack = 1
            if selfp.ip_port.source.stb == 1 and selfp.ip_port.source.sop == 1:
                print("packet from IP 0x{:08x}".format(selfp.ip_port.sink.ip_address))

            yield

if __name__ == "__main__":
    run_simulation(TB(), ncycles=2048, vcd_name="my.vcd", keep_files=True)
