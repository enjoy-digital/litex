from liteeth.common import *
from liteeth.mac.common import *
from liteeth.test.common import *

# PHY model
class PHYSource(PacketStreamer):
	def __init__(self, dw):
		PacketStreamer.__init__(self, eth_phy_description(dw))

class PHYSink(PacketLogger):
	def __init__(self, dw):
		PacketLogger.__init__(self, eth_phy_description(dw))

class PHY(Module):
	def __init__(self, dw, debug):
		self.dw = dw
		self.debug = debug

		self.submodules.phy_source = PHYSource(dw)
		self.submodules.phy_sink = PHYSink(dw)

		self.source = self.phy_source.source
		self.sink = self.phy_sink.sink

		self.mac_callback = None

	def set_mac_callback(self, callback):
		self.mac_callback = callback

	def send(self, datas):
		packet = Packet(datas)
		yield from self.phy_source.send(packet, blocking)

	def receive(self):
		yield from self.phy_sink.receive()
		self.packet = self.phy_sink.packet
