from liteeth.common import *
from liteeth.mac import LiteEthMAC
from liteeth.core.arp import LiteEthARP
from liteeth.core.ip import LiteEthIP
from liteeth.core.udp import LiteEthUDP

class LiteEthIPCore(Module, AutoCSR):
	def __init__(self, phy, mac_address, ip_address):
		self.submodules.mac = LiteEthMAC(phy, 8, interface="crossbar", with_hw_preamble_crc=True)
		self.submodules.arp = LiteEthARP(self.mac, mac_address, ip_address)
		self.submodules.ip = LiteEthIP(self.mac, mac_address, ip_address, self.arp.table)
		self.sink, self.source = self.ip.sink, self.ip.source

class LiteEthUDPIPCore(LiteEthIPCore):
	def __init__(self, phy, mac_address, ip_address):
		LiteEthIPCore.__init__(self, phy, mac_address, ip_address)
		self.submodules.udp = LiteEthUDP(self.ip, ip_address)
		self.sink, self.source = self.udp.sink, self.udp.source
