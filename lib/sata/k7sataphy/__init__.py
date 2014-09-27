from migen.fhdl.std import *
from migen.flow.actor import Sink, Source

from lib.sata.k7sataphy.std import *
from lib.sata.k7sataphy.gtx import K7SATAPHYGTX
from lib.sata.k7sataphy.crg import K7SATAPHYCRG
from lib.sata.k7sataphy.ctrl import K7SATAPHYHostCtrl, K7SATAPHYDeviceCtrl
from lib.sata.k7sataphy.datapath import K7SATAPHYRXAlign
from lib.sata.k7sataphy.datapath import K7SATAPHYRXConvert, K7SATAPHYTXConvert

class K7SATAPHY(Module):
	def __init__(self, pads, clk_freq, host=True, default_speed="SATA3"):
		self.sink = Sink([("d", 32)])
		self.source = Source([("d", 32)])

	# GTX
		gtx = K7SATAPHYGTX(pads, default_speed)
		self.submodules += gtx

	# CRG / CTRL
		crg = K7SATAPHYCRG(pads, gtx, clk_freq, default_speed)
		if host:
			ctrl = K7SATAPHYHostCtrl(gtx, clk_freq)
		else:
			ctrl = K7SATAPHYDeviceCtrl(gtx, clk_freq)
		self.submodules += crg, ctrl
		self.comb += ctrl.start.eq(crg.ready)

	# DATAPATH
		rxalign = K7SATAPHYRXAlign()
		rxconvert = K7SATAPHYRXConvert()
		txconvert = K7SATAPHYTXConvert()
		self.submodules += rxalign, rxconvert, txconvert
		self.comb += [
			rxalign.rxdata_i.eq(gtx.rxdata),
			rxalign.rxcharisk_i.eq(gtx.rxcharisk),
			rxconvert.rxdata.eq(rxalign.rxdata_o),
			rxconvert.rxcharisk.eq(rxalign.rxcharisk_o),

			gtx.txdata.eq(txconvert.txdata),
			gtx.txcharisk.eq(txconvert.txcharisk)
		]

		self.comb += [
			If(ctrl.ready,
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
