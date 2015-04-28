from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core import LiteEthUDPIPCore
from misoclib.com.liteeth.frontend.etherbone import LiteEthEtherbone

from misoclib.com.liteeth.test.common import *
from misoclib.com.liteeth.test.model import phy, mac, arp, ip, udp, etherbone

ip_address = 0x12345678
mac_address = 0x12345678abcd


class TB(Module):
    def __init__(self):
        self.submodules.phy_model = phy.PHY(8, debug=False)
        self.submodules.mac_model = mac.MAC(self.phy_model, debug=False, loopback=False)
        self.submodules.arp_model = arp.ARP(self.mac_model, mac_address, ip_address, debug=False)
        self.submodules.ip_model = ip.IP(self.mac_model, mac_address, ip_address, debug=False, loopback=False)
        self.submodules.udp_model = udp.UDP(self.ip_model, ip_address, debug=False, loopback=False)
        self.submodules.etherbone_model = etherbone.Etherbone(self.udp_model, debug=False)

        self.submodules.core = LiteEthUDPIPCore(self.phy_model, mac_address, ip_address, 100000)
        self.submodules.etherbone = LiteEthEtherbone(self.core.udp, 20000)

        self.submodules.sram = wishbone.SRAM(1024)
        self.submodules.interconnect = wishbone.InterconnectPointToPoint(self.etherbone.master.bus, self.sram.bus)

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

        test_probe = True
        test_writes = True
        test_reads = True

        # test probe
        if test_probe:
            packet = etherbone.EtherbonePacket()
            packet.pf = 1
            self.etherbone_model.send(packet)
            yield from self.etherbone_model.receive()
            print("probe: " + str(bool(self.etherbone_model.rx_packet.pr)))

        for i in range(8):
            # test writes
            if test_writes:
                writes_datas = [j for j in range(16)]
                writes = etherbone.EtherboneWrites(base_addr=0x1000,
                                                   datas=writes_datas)
                record = etherbone.EtherboneRecord()
                record.writes = writes
                record.reads = None
                record.bca = 0
                record.rca = 0
                record.rff = 0
                record.cyc = 0
                record.wca = 0
                record.wff = 0
                record.byte_enable = 0xf
                record.wcount = len(writes_datas)
                record.rcount = 0

                packet = etherbone.EtherbonePacket()
                packet.records = [record]
                self.etherbone_model.send(packet)
                for i in range(256):
                    yield

            # test reads
            if test_reads:
                reads_addrs = [0x1000 + 4*j for j in range(16)]
                reads = etherbone.EtherboneReads(base_ret_addr=0x1000,
                                                 addrs=reads_addrs)
                record = etherbone.EtherboneRecord()
                record.writes = None
                record.reads = reads
                record.bca = 0
                record.rca = 0
                record.rff = 0
                record.cyc = 0
                record.wca = 0
                record.wff = 0
                record.byte_enable = 0xf
                record.wcount = 0
                record.rcount = len(reads_addrs)

                packet = etherbone.EtherbonePacket()
                packet.records = [record]
                self.etherbone_model.send(packet)
                yield from self.etherbone_model.receive()
                loopback_writes_datas = []
                loopback_writes_datas = self.etherbone_model.rx_packet.records.pop().writes.get_datas()

                # check results
                s, l, e = check(writes_datas, loopback_writes_datas)
                print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
    run_simulation(TB(), ncycles=4096, vcd_name="my.vcd", keep_files=True)
