from liteeth.common import *

class LiteEthUDPMasterPort:
	def __init__(self, dw):
		self.dw = dw
		self.source = Source(eth_udp_user_description(dw))
		self.sink = Sink(eth_udp_user_description(dw))

	def connect(self, slave):
		return [
			Record.connect(self.source, slave.sink),
			Record.connect(slave.source, self.sink)
		]

class LiteEthUDPSlavePort:
	def __init__(self, dw):
		self.dw =dw
		self.sink = Sink(eth_udp_user_description(dw))
		self.source = Source(eth_udp_user_description(dw))

	def connect(self, master):
		return [
			Record.connect(self.sink, master.source),
			Record.connect(master.sink, self.source)
		]

class LiteEthUDPUserPort(LiteEthUDPSlavePort):
	def __init__(self, dw):
		LiteEthUDPSlavePort.__init__(self, dw)
