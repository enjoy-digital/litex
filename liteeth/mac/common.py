from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer
from liteeth.generic.crossbar import LiteEthCrossbar

class LiteEthMACDepacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_phy_description(8),
			eth_mac_description(8),
			mac_header,
			mac_header_len)

class LiteEthMACPacketizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_mac_description(8),
			eth_phy_description(8),
			mac_header,
			mac_header_len)

class LiteEthMACMasterPort:
	def __init__(self, dw):
		self.source = Source(eth_mac_description(dw))
		self.sink = Sink(eth_mac_description(dw))

	def connect(self, slave):
		return [
			Record.connect(self.source, slave.sink),
			Record.connect(slave.source, self.sink)
		]

class LiteEthMACSlavePort:
	def __init__(self, dw):
		self.sink = Sink(eth_mac_description(dw))
		self.source = Source(eth_mac_description(dw))

	def connect(self, master):
		return [
			Record.connect(self.sink, master.source),
			Record.connect(master.sink, self.source)
		]

class LiteEthMACUserPort(LiteEthMACSlavePort):
	def __init__(self, dw):
		LiteEthMACSlavePort.__init__(self, dw)

class LiteEthMACCrossbar(LiteEthCrossbar):
	def __init__(self):
		LiteEthCrossbar.__init__(self, LiteEthMACMasterPort, "ethernet_type")

	def get_port(self, ethernet_type):
		port = LiteEthMACUserPort(8)
		if ethernet_type in self.users.keys():
			raise ValueError("Ethernet type {0:#x} already assigned".format(ethernet_type))
		self.users[ethernet_type] = port
		return port
