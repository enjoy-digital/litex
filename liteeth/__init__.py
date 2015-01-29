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
		self.submodules.unknown_sink = unknown_sink = Sink(eth_mac_description(8))
		self.comb += unknown_sink.ack.eq(1)
		self.submodules.mac_dispatcher = mac_dispatcher = Dispatcher(mac.source, [arp.sink, ip.sink, unknown_sink])
		self.comb += [
			If(mac.source.eth_type == ethernet_type_arp,
				mac_dispatcher.sel.eq(0)
			).Elif(mac.source.eth_type == ethernet_type_ip,
				mac_dispatcher.sel.eq(1)
			).Else(
				mac_dispatcher.sel.eq(2) # connect to unknown sink that always acknowledge data
			)
		]
		# MAC arbitrate
		self.submodules.mac_arbiter = mac_arbiter = Arbiter([arp.source, ip.source], mac.sink)


