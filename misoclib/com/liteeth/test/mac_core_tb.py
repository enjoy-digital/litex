from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core.mac.core import LiteEthMACCore

from misoclib.com.liteeth.test.common import *
from misoclib.com.liteeth.test.model import phy, mac


class TB(Module):
    def __init__(self):
        self.submodules.phy_model = phy.PHY(8, debug=False)
        self.submodules.mac_model = mac.MAC(self.phy_model, debug=False, loopback=True)
        self.submodules.core = LiteEthMACCore(phy=self.phy_model, dw=8, with_preamble_crc=True)

        self.submodules.streamer = PacketStreamer(eth_phy_description(8), last_be=1)
        self.submodules.streamer_randomizer = AckRandomizer(eth_phy_description(8), level=50)

        self.submodules.logger_randomizer = AckRandomizer(eth_phy_description(8), level=50)
        self.submodules.logger = PacketLogger(eth_phy_description(8))

        # use sys_clk for each clock_domain
        self.clock_domains.cd_eth_rx = ClockDomain()
        self.clock_domains.cd_eth_tx = ClockDomain()
        self.comb += [
            self.cd_eth_rx.clk.eq(ClockSignal()),
            self.cd_eth_rx.rst.eq(ResetSignal()),
            self.cd_eth_tx.clk.eq(ClockSignal()),
            self.cd_eth_tx.rst.eq(ResetSignal()),
        ]

        self.comb += [
            Record.connect(self.streamer.source, self.streamer_randomizer.sink),
            Record.connect(self.streamer_randomizer.source, self.core.sink),
            Record.connect(self.core.source, self.logger_randomizer.sink),
            Record.connect(self.logger_randomizer.source, self.logger.sink)
        ]

    def gen_simulation(self, selfp):
        selfp.cd_eth_rx.rst = 1
        selfp.cd_eth_tx.rst = 1
        yield
        selfp.cd_eth_rx.rst = 0
        selfp.cd_eth_tx.rst = 0

        for i in range(8):
            packet = mac.MACPacket([i for i in range(64)])
            packet.target_mac = 0x010203040506
            packet.sender_mac = 0x090A0B0C0C0D
            packet.ethernet_type = 0x0800
            packet.encode_header()
            yield from self.streamer.send(packet)
            yield from self.logger.receive()

            # check results
            s, l, e = check(packet, self.logger.packet)
            print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
    run_simulation(TB(), ncycles=4000, vcd_name="my.vcd", keep_files=True)
