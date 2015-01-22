from migen.genlib.resetsync import AsyncResetSynchronizer

from litesata.common import *
from litesata.phy import LiteSATAPHY
from litesata import LiteSATA

class _CRG(Module):
	def __init__(self, platform):
		self.cd_sys = ClockDomain()

class LiteSATACore(Module):
	default_platform = "verilog_backend"

	def __init__(self, platform):
		clk_freq = 166*1000000
		self.crg = _CRG(platform)

		# SATA PHY/Core/Frontend
		self.sata_phy = LiteSATAPHY(platform.device, platform.request("sata"), "SATA2", clk_freq)
		self.sata = LiteSATA(self.sata_phy)

		# Get user ports from crossbar
		self.user_ports = self.sata.crossbar.get_ports(4)

	def get_ios(self):
		# clock / reset
		ios = {self.crg.cd_sys.clk, self.crg.cd_sys.rst}

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

		sink_layout = command_tx_description(32).get_full_layout()
		source_layout = command_rx_description(32).get_full_layout()

		for port in self.user_ports:
			for e in _iter_layout(sink_layout):
					obj = getattr(port.sink, e[0])
					ios = ios.union({obj})
			for e in _iter_layout(source_layout):
					obj = getattr(port.source, e[0])
					ios = ios.union({obj})
		return ios


default_subtarget = LiteSATACore
