from liteeth.common import *
from liteeth.mac import LiteEthMAC
from liteeth.core.arp import LiteEthARP
from liteeth.core.ip import LiteEthIP

class LiteEthIPCore(Module, AutoCSR):
	def __init__(self, phy, mac_address, ip_address):
		self.phy = phy
		self.submodules.mac = mac = LiteEthMAC(phy, 8, interface="crossbar", with_hw_preamble_crc=True)
		self.submodules.arp = arp = LiteEthARP(mac, mac_address, ip_address)
		self.submodules.ip = ip = LiteEthIP(mac, mac_address, ip_address, arp.table)
		self.sink, self.source = self.ip.sink, self.ip.source
