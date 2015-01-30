from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer
from liteeth.mac.core import LiteEthMACCore
from liteeth.mac.frontend.wishbone import LiteEthMACWishboneInterface
from liteeth.mac.frontend.crossbar import LiteEthMACCrossbar

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
	def __init__(self, phy, dw, interface="crossbar", endianness="be",
			with_hw_preamble_crc=True):
		self.submodules.core = LiteEthMACCore(phy, dw, endianness, with_hw_preamble_crc)
		self.csrs = None
		if interface == "crossbar":
			self.submodules.crossbar = LiteEthMACCrossbar()
			self.submodules.packetizer = LiteEthMACPacketizer()
			self.submodules.depacketizer = LiteEthMACDepacketizer()
			self.comb += [
				Record.connect(self.crossbar.master.source, self.packetizer.sink),
				Record.connect(self.packetizer.source, self.core.sink),
				Record.connect(self.core.source, self.depacketizer.sink),
				Record.connect(self.depacketizer.source, self.crossbar.master.sink)
			]
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
			raise ValueError(interface + " not supported by LiteEthMac!")

	def get_csrs(self):
		return self.csrs
