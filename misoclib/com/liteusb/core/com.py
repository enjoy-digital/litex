from migen.fhdl.std import *
from migen.flow.actor import *

from misoclib.com.liteusb.common import *
from misoclib.com.liteusb.frontend.crossbar import FtdiCrossbar
from misoclib.com.liteusb.core.packetizer import FtdiPacketizer
from misoclib.com.liteusb.core.depacketizer import FtdiDepacketizer
from misoclib.com.liteusb.phy.ft2232h import FtdiPHY

class FtdiCom(Module):
	def __init__(self, pads, *ports):
		# crossbar
		self.submodules.crossbar = FtdiCrossbar(list(ports))

		# packetizer / depacketizer
		self.submodules.packetizer = FtdiPacketizer()
		self.submodules.depacketizer = FtdiDepacketizer()
		self.comb += [
			self.crossbar.slave.source.connect(self.packetizer.sink),
			self.depacketizer.source.connect(self.crossbar.slave.sink)
		]

		# phy
		self.submodules.phy = FtdiPHY(pads)
		self.comb += [
			self.packetizer.source.connect(self.phy.sink),
			self.phy.source.connect(self.depacketizer.sink)
		]
