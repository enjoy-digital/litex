from migen.fhdl.std import *

from lib.sata.k7sataphy.std import *
from lib.sata.k7sataphy.gtx import GTXE2_CHANNEL
from lib.sata.k7sataphy.clocking import K7SATAPHYClocking

class K7SATAPHY(Module):
	def __init__(self, pads, dw=16):
		self.sink = Sink([("d", dw)], True)
		self.source = Source([("d", dw)], True)

		self.submodules.gtx = GTXE2_CHANNEL(pads, "SATA3")
		self.submodules.clocking = K7SATAPHYClocking(pads, self.gtx)


