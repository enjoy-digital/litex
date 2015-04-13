from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core import LiteEthIPCore

from misoclib.com.liteeth.test.common import *
from misoclib.com.liteeth.test.model.dumps import *
from misoclib.com.liteeth.test.model.mac import *
from misoclib.com.liteeth.test.model.ip import *
from misoclib.com.liteeth.test.model.icmp import *
from misoclib.com.liteeth.test.model import phy, mac, arp, ip, icmp

ip_address = 0x12345678
mac_address = 0x12345678abcd


class TB(Module):
    def __init__(self):
        self.submodules.phy_model = phy.PHY(8, debug=True)
        self.submodules.mac_model = mac.MAC(self.phy_model, debug=True, loopback=False)
        self.submodules.arp_model = arp.ARP(self.mac_model, mac_address, ip_address, debug=True)
        self.submodules.ip_model = ip.IP(self.mac_model, mac_address, ip_address, debug=True, loopback=False)
        self.submodules.icmp_model = icmp.ICMP(self.ip_model, ip_address, debug=True)

        self.submodules.ip = LiteEthIPCore(self.phy_model, mac_address, ip_address, 100000)

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

        packet = MACPacket(ping_request)
        packet.decode_remove_header()
        packet = IPPacket(packet)
        packet.decode()
        packet = ICMPPacket(packet)
        packet.decode()
        self.icmp_model.send(packet)

if __name__ == "__main__":
    run_simulation(TB(), ncycles=2048, vcd_name="my.vcd", keep_files=True)
