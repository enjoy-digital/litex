from migen.genlib.resetsync import AsyncResetSynchronizer

from litesata.common import *
from litesata.phy import LiteSATAPHY
from litesata import LiteSATA

class LiteSATACore(Module):
	default_platform = "verilog_backend"
	def __init__(self, platform, clk_freq=166*1000000, nports=4):
		self.clk_freq = clk_freq

		# SATA PHY/Core/Frontend
		self.submodules.sata_phy = LiteSATAPHY(platform.device, platform.request("sata"), "sata_gen2", clk_freq)
		self.submodules.sata = LiteSATA(self.sata_phy)

		# Get user ports from crossbar
		self.user_ports = self.sata.crossbar.get_ports(nports)

	def get_ios(self):
		ios = set()

		# Transceiver
		for e in dir(self.sata_phy.pads):
			obj = getattr(self.sata_phy.pads, e)
			if isinstance(obj, Signal):
				ios = ios.union({obj})

		# User ports
		def _iter_layout(layout):
			for e in layout:
				if isinstance(e[1], list):
					yield from _iter_layout(e[1])
				else:
					yield e

		for port in self.user_ports:
			for endpoint in [port.sink, port.source]:
				for e in _iter_layout(endpoint.layout):
					obj = getattr(endpoint, e[0])
					ios = ios.union({obj})
		return ios


default_subtarget = LiteSATACore
