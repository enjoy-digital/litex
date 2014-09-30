from migen.fhdl.std import *
from migen.genlib.misc import chooser
from migen.actorlib.fifo import AsyncFIFO
from migen.flow.actor import Sink, Source

from lib.sata.k7sataphy.std import *

class K7SATAPHYDatapathRX(Module):
	def __init__(self):
		self.sink = Sink([("data", 16), ("charisk", 2)])
		self.source = Source([("data", 32), ("charisk", 4)])

		###

	# bytes alignment
		
		# shift register
		data_sr = Signal(32+8)
		charisk_sr = Signal(4+1)
		data_sr_d = Signal(32+8)
		charisk_sr_d = Signal(4+1)
		self.comb += [
			data_sr.eq(Cat(self.sink.payload.data, data_sr_d)),
			charisk_sr.eq(Cat(self.sink.payload.charisk, charisk_sr_d))
		]
		self.sync.sata_rx += [
			data_sr_d.eq(data_sr),
			charisk_sr_d.eq(charisk_sr)
		]

		# alignment
		alignment = Signal()
		valid = Signal()
		self.sync.sata_rx += [
			If(self.sink.payload.charisk !=0,
				alignment.eq(self.sink.payload.charisk[1]),
				valid.eq(0)
			).Else(
				valid.eq(~valid)
			)
		]

		# 16 to 32
		data = Signal(32)
		charisk = Signal(4)
		self.comb += [
			If(~alignment,
				data.eq(data_sr[0:32]),
				charisk.eq(charisk_sr[0:4])
			).Else(
				data.eq(data_sr[8:40]),
				charisk.eq(charisk_sr[1:5])
			)
		]

	# clock domain crossing
		# (SATA3) 300MHz sata_rx clk to sys_clk
		# (SATA2) 150MHz sata_rx clk to sys_clk
		# (SATA1) 75MHz sata_rx clk to sys_clk
		# requirements:
		# due to the convertion ratio of 2, sys_clk need to be > sata_rx/2
		# source destination is always able to accept data (ack always 1)
		fifo = AsyncFIFO([("data", 32), ("charisk", 4)], 16)
		self.submodules.fifo = RenameClockDomains(fifo, {"write": "sata_rx", "read": "sys"})
		self.comb += [
			fifo.sink.stb.eq(valid),
			fifo.sink.payload.data.eq(data),
			fifo.sink.payload.charisk.eq(charisk),
		]
		self.comb += Record.connect(fifo.source, self.source)

class K7SATAPHYDatapathTX(Module):
	def __init__(self):
		self.sink = Sink([("data", 32), ("charisk", 4)])
		self.source = Source([("data", 16), ("charisk", 2)])

		###

	# clock domain crossing
		# (SATA3) sys_clk to 300MHz sata_tx clk
		# (SATA2) sys_clk to 150MHz sata_tx clk
		# (SATA1) sys_clk to 75MHz sata_tx clk
		# requirements:
		# source destination is always able to accept data (ack always 1)
		fifo = AsyncFIFO([("data", 32), ("charisk", 4)], 16)
		self.submodules.fifo = RenameClockDomains(fifo, {"write": "sys", "read": "sata_tx"})
		self.comb += Record.connect(self.sink, fifo.sink)

		# 32 to 16
		mux = Signal()
		last = Signal()
		self.comb += [
			last.eq(mux == 1),
			self.source.stb.eq(fifo.source.stb),
			fifo.source.ack.eq(last),
		]
		self.sync.sata_tx += [
			If(self.source.stb,
				If(last,
					mux.eq(0)
				).Else(
					mux.eq(mux + 1)
				)
			)
		]
		self.comb += [
			chooser(fifo.source.payload.data, mux, self.source.payload.data),
			chooser(fifo.source.payload.charisk, mux, self.source.payload.charisk)
		]

class K7SATAPHYDatapath(Module):
	def __init__(self, gtx, ctrl):
		self.sink = Sink([("d", 32)])
		self.source = Source([("d", 32)])

		###

	# change data width & cross domain crossing
		rx = K7SATAPHYDatapathRX()
		tx = K7SATAPHYDatapathTX()
		self.submodules += rx, tx
		self.comb += [
			rx.sink.payload.data.eq(gtx.rxdata),
			rx.sink.payload.charisk.eq(gtx.rxcharisk),

			gtx.txdata.eq(tx.source.payload.data),
			gtx.txcharisk.eq(tx.source.payload.charisk),
		]

	# user / ctrl mux
		self.comb += [
			# user
			If(ctrl.ready,
				tx.sink.stb.eq(self.sink.stb),
				tx.sink.payload.data.eq(self.sink.payload.d),
				tx.sink.payload.charisk.eq(0),
				self.sink.ack.eq(tx.sink.ack),

				self.source.stb.eq(rx.source.stb),
				self.source.payload.d.eq(rx.source.payload.data),
				rx.source.ack.eq(1),
			# ctrl
			).Else(
				tx.sink.stb.eq(1),
				tx.sink.payload.data.eq(ctrl.txdata),
				tx.sink.payload.charisk.eq(ctrl.txcharisk),

				ctrl.rxdata.eq(rx.source.payload.data),
				rx.source.ack.eq(1),
			)			
		]
