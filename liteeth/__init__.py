from liteeth.common import *
from liteeth.generic.arbiter import Arbiter
from liteeth.generic.dispatcher import Dispatcher
from liteeth.mac import LiteEthMAC

class LiteEthIPStack(Module, AutoCSR):
	def __init__(self, phy):
		self.phy = phy
		self.submodules.mac = mac = LiteEthMAC(phy, 8, interface="mac", with_hw_preamble_crc=True)
		self.submodules.arp = arp = LiteEthARP()
		self.submodules.ip = ip = LiteEthMACIP()

		# MAC dispatch
		self.submodules.mac_dispatcher = mac_dispatcher = Dispatcher(mac.source, [arp.sink, ip.sink], one_hot=True)
		self.comb += [
			If(mac.source.eth_type == ethernet_type_arp,
				mac_dispatcher.sel.eq(1)
			).Elif(mac.source.eth_type == ethernet_type_ip,
				mac_dispatcher.sel.eq(2)
			)
		]
		# MAC arbitrate
		self.submodules.mac_arbiter = mac_arbiter = Arbiter([arp.source, ip.source], mac.sink)


