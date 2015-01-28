from liteeth.common import *
from liteeth.mac.core import LiteEthMACCore
from liteeth.mac.frontend import wishbone

class LiteEthMAC(Module, AutoCSR):
	def __init__(self, phy, interface="wishbone", dw, endianness="be",
			with_hw_preamble_crc=True):
		self.submodules.core = LiteEthMACCore(phy, endianness, with_hw_preamble)
		if interface == "wishbone":
			self.interface = wishbone.LiteETHMACWishboneInterface(), dw, nrxslots, ntxslots)
		elif interface == "dma":
			raise NotImplementedError
		elif interface == "core":
			self.sink = self.core.sink
			self.source = self.core.source
		else:
			raise ValueError("EthMAC only supports Wishbone, DMA or core interfaces")
