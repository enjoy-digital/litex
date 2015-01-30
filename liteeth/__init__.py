from liteeth.common import *
from liteeth.generic.arbiter import Arbiter
from liteeth.generic.dispatcher import Dispatcher
from liteeth.mac import LiteEthMAC
from liteeth.arp import LiteEthARP
from liteeth.ip import LiteEthIP

class LiteEthIPStack(Module, AutoCSR):
	def __init__(self, phy, mac_address, ip_address):
		self.phy = phy
		self.submodules.mac = mac = LiteEthMAC(phy, 8, interface="mac", with_hw_preamble_crc=True)
		self.submodules.arp = arp = LiteEthARP(mac_address, ip_address)
		self.submodules.ip = ip = LiteEthIP(ip_address, arp.table)

		# MAC dispatch
		self.submodules.mac_dispatcher = Dispatcher(mac.source, [arp.sink, ip.sink], one_hot=True)
		self.comb += \
			Case(mac.source.ethernet_type, {
				ethernet_type_arp	: [self.mac_dispatcher.sel.eq(1)],
				ethernet_type_ip	: [self.mac_dispatcher.sel.eq(2)],
				"default"			: [self.mac_dispatcher.sel.eq(0)],
			})
		# MAC arbitrate
		self.submodules.mac_arbiter = Arbiter([arp.source, ip.source], mac.sink)
