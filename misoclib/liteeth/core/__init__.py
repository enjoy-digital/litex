from misoclib.liteeth.common import *
from misoclib.liteeth.generic import *
from misoclib.liteeth.mac import LiteEthMAC
from misoclib.liteeth.core.arp import LiteEthARP
from misoclib.liteeth.core.ip import LiteEthIP
from misoclib.liteeth.core.udp import LiteEthUDP
from misoclib.liteeth.core.icmp import LiteEthICMP

class LiteEthIPCore(Module, AutoCSR):
	def __init__(self, phy, mac_address, ip_address, clk_freq):
		self.submodules.mac = LiteEthMAC(phy, 8, interface="crossbar", with_hw_preamble_crc=True)
		self.submodules.arp = LiteEthARP(self.mac, mac_address, ip_address, clk_freq)
		self.submodules.ip = LiteEthIP(self.mac, mac_address, ip_address, self.arp.table)
		self.submodules.icmp = LiteEthICMP(self.ip, ip_address)

class LiteEthUDPIPCore(LiteEthIPCore):
	def __init__(self, phy, mac_address, ip_address, clk_freq):
		LiteEthIPCore.__init__(self, phy, mac_address, ip_address, clk_freq)
		self.submodules.udp = LiteEthUDP(self.ip, ip_address)
