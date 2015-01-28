from liteeth.common import *
from liteeth.mac.core import LiteEthMACCore
from liteeth.mac.frontend import wishbone

class LiteEthMAC(Module, AutoCSR):
	def __init__(self, phy, dw, interface="core", endianness="be",
			with_hw_preamble_crc=True):
		self.submodules.core = LiteEthMACCore(phy, dw, endianness, with_hw_preamble_crc)
		self.csrs = None
		if interface == "core":
			self.sink, self.source = self.core.sink, self.core.source
		elif interface == "wishbone":
			self.interface = wishbone.LiteEthMACWishboneInterface(dw, 2, 2)
			self.ev, self.bus = self.interface.sram.ev, self.interface.bus
			self.csrs = self.interface.get_csrs()
		elif interface == "dma":
			raise NotImplementedError
		else:
			raise ValueError(inteface + " not supported by LiteEthMac!")

	def get_csrs(self):
		return self.csrs
