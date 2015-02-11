from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation

from liteeth.common import *
from liteeth.core import LiteEthUDPIPCore
from liteeth.core.etherbone import LiteEthEtherbone

from liteeth.test.common import *
from liteeth.test.model import phy, mac, arp, ip, udp, etherbone

ip_address = 0x12345678
mac_address = 0x12345678abcd

class TB(Module):
	def __init__(self):
		self.submodules.phy_model = phy.PHY(8, debug=True)
		self.submodules.mac_model = mac.MAC(self.phy_model, debug=True, loopback=False)
		self.submodules.arp_model = arp.ARP(self.mac_model, mac_address, ip_address, debug=False)
		self.submodules.ip_model = ip.IP(self.mac_model, mac_address, ip_address, debug=True, loopback=False)
		self.submodules.udp_model = udp.UDP(self.ip_model, ip_address, debug=True, loopback=False)
		self.submodules.etherbone_model = etherbone.Etherbone(self.udp_model, debug=True)

		self.submodules.core = LiteEthUDPIPCore(self.phy_model, mac_address, ip_address, 100000)
		self.submodules.etherbone = LiteEthEtherbone(self.core.udp, 20000)

		self.submodules.sram = wishbone.SRAM(1024)
		self.submodules.interconnect = wishbone.InterconnectPointToPoint(self.etherbone.wishbone.bus, self.sram.bus)



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

		# test probe
		#packet = etherbone.EtherbonePacket()
		#packet.pf = 1
		#self.etherbone_model.send(packet)

		# test writes
		writes = etherbone.EtherboneWrites(base_addr=0x1000)
		for i in range(16):
			writes.add(etherbone.EtherboneWrite(i))
		record = etherbone.EtherboneRecord()
		record.writes = writes
		record.reads = None
		record.bca = 0
		record.rca = 0
		record.rff = 0
		record.cyc = 0
		record.wca = 0
		record.wff = 0
		record.byte_enable = 0
		record.wcount = 16
		record.rcount = 0

		packet = etherbone.EtherbonePacket()
		packet.records = [record]
		print(packet)

		self.etherbone_model.send(packet)



if __name__ == "__main__":
	run_simulation(TB(), ncycles=1024, vcd_name="my.vcd", keep_files=True)