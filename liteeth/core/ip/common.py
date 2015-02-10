from liteeth.common import *

class LiteEthIPV4MasterPort:
	def __init__(self, dw):
		self.dw = dw
		self.source = Source(eth_ipv4_user_description(dw))
		self.sink = Sink(eth_ipv4_user_description(dw))

	def connect(self, slave):
		return [
			Record.connect(self.source, slave.sink),
			Record.connect(slave.source, self.sink)
		]

class LiteEthIPV4SlavePort:
	def __init__(self, dw):
		self.dw = dw
		self.sink = Sink(eth_ipv4_user_description(dw))
		self.source = Source(eth_ipv4_user_description(dw))

	def connect(self, master):
		return [
			Record.connect(self.sink, master.source),
			Record.connect(master.sink, self.source)
		]

class LiteEthIPV4UserPort(LiteEthIPV4SlavePort):
	def __init__(self, dw):
		LiteEthIPV4SlavePort.__init__(self, dw)
