from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core.mac import LiteEthMAC
from misoclib.com.liteeth.core.arp import LiteEthARP

from misoclib.com.liteeth.test.common import *
from misoclib.com.liteeth.test.model import phy, mac, arp

ip_address = 0x12345678
mac_address = 0x12345678abcd


class TB(Module):
    def __init__(self):
        self.submodules.phy_model = phy.PHY(8, debug=False)
        self.submodules.mac_model = mac.MAC(self.phy_model, debug=False, loopback=False)
        self.submodules.arp_model = arp.ARP(self.mac_model, mac_address, ip_address, debug=False)

        self.submodules.mac = LiteEthMAC(self.phy_model, dw=8, with_preamble_crc=True)
        self.submodules.arp = LiteEthARP(self.mac, mac_address, ip_address, 100000)

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

        while selfp.arp.table.request.ack != 1:
            selfp.arp.table.request.stb = 1
            selfp.arp.table.request.ip_address = 0x12345678
            yield
        selfp.arp.table.request.stb = 0
        while selfp.arp.table.response.stb != 1:
            selfp.arp.table.response.ack = 1
            yield
        print("Received MAC : 0x{:12x}".format(selfp.arp.table.response.mac_address))


if __name__ == "__main__":
    run_simulation(TB(), ncycles=2048, vcd_name="my.vcd", keep_files=True)
