from migen.fhdl.std import *
from migen.flow.actor import Sink, Source

from lib.sata.k7sataphy.std import *
from lib.sata.k7sataphy.gtx import K7SATAPHYGTX
from lib.sata.k7sataphy.crg import K7SATAPHYCRG
from lib.sata.k7sataphy.ctrl import K7SATAPHYHostCtrl, K7SATAPHYDeviceCtrl
from lib.sata.k7sataphy.datapath import K7SATAPHYRXAlign
from lib.sata.k7sataphy.datapath import K7SATAPHYRXConvert, K7SATAPHYTXConvert

class K7SATAPHY(Module):
	def __init__(self, pads, clk_freq, host=True,):
		self.sink = Sink([("d", 32)], True)
		self.source = Source([("d", 32)], True)

		gtx = K7SATAPHYGTX(pads, "SATA3")
		self.comb += [
			gtx.rxrate.eq(0b000),
			gtx.txrate.eq(0b000),			
		]
		clocking = K7SATAPHYCRG(pads, gtx, clk_freq)
		rxalign = K7SATAPHYRXAlign()
		rxconvert = K7SATAPHYRXConvert()
		txconvert = K7SATAPHYTXConvert()
		self.submodules += gtx, clocking, rxalign, rxconvert, txconvert
		self.comb += [
			rxalign.rxdata_i.eq(gtx.rxdata),
			rxalign.rxcharisk_i.eq(gtx.rxcharisk),
			rxconvert.rxdata.eq(rxalign.rxdata_o),
			rxconvert.rxcharisk.eq(rxalign.rxcharisk_o),

			gtx.txdata.eq(txconvert.txdata),
			gtx.txcharisk.eq(txconvert.txcharisk)
		]

		if host:
			ctrl = K7SATAPHYHostCtrl(gtx)
		else:
			ctrl = K7SATAPHYDeviceCtrl(gtx)
		self.submodules += ctrl
		self.comb += [
			If(ctrl.link_up,
				txconvert.sink.stb.eq(self.sink.stb),
				txconvert.sink.data.eq(self.sink.d),
				txconvert.sink.charisk.eq(0),
				self.sink.ack.eq(txconvert.sink.ack),
			).Else(
				txconvert.sink.stb.eq(1),
				txconvert.sink.data.eq(ctrl.txdata),
				txconvert.sink.charisk.eq(ctrl.txcharisk)
			),
			self.source.stb.eq(rxconvert.source.stb),
			self.source.payload.eq(rxconvert.source.payload),
			rxconvert.source.ack.eq(self.source.ack),
			ctrl.rxdata.eq(rxconvert.source.data)
		]
