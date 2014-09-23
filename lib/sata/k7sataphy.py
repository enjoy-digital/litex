from migen.fhdl.std import *

from lib.sata import GTXE2_CHANNEL, GTXE2_COMMON

class K7SATAPHY(Module):
	def __init__(self, pads):
		self.submodules.gtxe2_channel = GTXE2_CHANNEL(pads, "SATA_III")
		self.submodules.gtxe2_common = GTXE2_COMMON(16)
