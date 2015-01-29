from liteeth.common import *
from liteeth.mac.core import LiteEthMACCore
from liteeth.mac.frontend import wishbone
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

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

class LiteEthMAC(Module, AutoCSR):
	def __init__(self, phy, dw, interface="mac", endianness="be",
			with_hw_preamble_crc=True):
		self.submodules.core = LiteEthMACCore(phy, dw, endianness, with_hw_preamble_crc)
		self.csrs = None
		if interface == "mac":
			packetizer = LiteEthMACPacketizer()
			depacketizer = LiteEthMACDepacketizer()
			self.submodules += packetizer, depacketizer
			self.comb += [
				Record.connect(packetizer.source, self.core.sink),
				Record.connect(self.core.source, depacketizer.sink)
			]
			self.sink, self.source = packetizer.sink, depacketizer.source
			pass
		elif interface == "wishbone":
			self.submodules.interface = wishbone.LiteEthMACWishboneInterface(dw, 2, 2)
			self.comb += [
				Record.connect(self.interface.source, self.core.sink),
				Record.connect(self.core.source, self.interface.sink)
			]
			self.ev, self.bus = self.interface.sram.ev, self.interface.bus
			self.csrs = self.interface.get_csrs()
		elif interface == "dma":
			raise NotImplementedError
		else:
			raise ValueError(inteface + " not supported by LiteEthMac!")

	def get_csrs(self):
		return self.csrs
