from migen.fhdl.std import *
from migen.flow.actor import Sink, Source

from lib.sata.k7sataphy.std import *
from lib.sata.k7sataphy.gtx import GTXE2_CHANNEL
from lib.sata.k7sataphy.clocking import K7SATAPHYClocking
from lib.sata.k7sataphy.ctrl import K7SATAPHYHostCtrl, K7SATAPHYDeviceCtrl

class K7SATAPHY(Module):
	def __init__(self, pads, host=True):
		self.sink = Sink([("d", 32)], True)
		self.source = Source([("d", 32)], True)

		self.submodules.gtx = GTXE2_CHANNEL(pads, "SATA3")
		self.submodules.clocking = K7SATAPHYClocking(pads, self.gtx)
		if host:
			self.submodules.ctrl = K7SATAPHYHostCtrl(self.gtx)
		else:
			self.submodules.ctrl = K7SATAPHYDeviceCtrl(self.gtx)
		self.comb += [
			If(self.ctrl.link_up,
				self.gtx.sink.stb.eq(self.sink.stb),
				self.gtx.sink.data.eq(self.sink.d),
				self.gtx.sink.charisk.eq(0),
				self.sink.ack.eq(self.gtx.sink.ack),
			).Else(
				self.gtx.sink.stb.eq(1),
				self.gtx.sink.data.eq(self.ctrl.txdata),
				self.gtx.sink.charisk.eq(self.ctrl.txcharisk)
			),
			self.source.stb.eq(self.gtx.source.stb),
			self.source.payload.eq(self.gtx.source.payload),
			self.gtx.source.ack.eq(self.source.ack),
			self.ctrl.rxdata.eq(self.gtx.source.data)
		]
