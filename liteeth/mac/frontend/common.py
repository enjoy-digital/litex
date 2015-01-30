from liteeth.common import *

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
