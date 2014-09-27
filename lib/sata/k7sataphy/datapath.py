from migen.fhdl.std import *
from migen.actorlib.fifo import AsyncFIFO
from migen.actorlib.structuring import Converter
from migen.flow.actor import Sink, Source

from lib.sata.k7sataphy.std import *

class K7SATAPHYRXAlign(Module):
	def __init__(self, dw=16):
		self.rxdata_i = Signal(dw)
		self.rxcharisk_i = Signal(dw//8)

		self.rxdata_o = Signal(dw)
		self.rxcharisk_o = Signal(dw//8)

		###

		rxdata_r = Signal(dw)
		rxcharisk_r = Signal(dw//8)
		self.sync.sata_rx += [
			rxdata_r.eq(self.rxdata_i),
			rxcharisk_r.eq(self.rxcharisk_i)
		]
		cases = {}
		cases[1<<0] = [
				self.rxdata_o.eq(rxdata_r[0:dw]),
				self.rxcharisk_o.eq(rxcharisk_r[0:dw//8])
		]
		for i in range(1, dw//8):
			cases[1<<i] = [
				self.rxdata_o.eq(Cat(self.rxdata_i[8*i:dw], rxdata_r[0:8*i])),
				self.rxcharisk_o.eq(Cat(self.rxcharisk_i[i:dw//8], rxcharisk_r[0:i]))
			]
		self.comb += Case(rxcharisk_r, cases)

class K7SATAPHYRXConvert(Module):
	def __init__(self):
		self.rxdata = Signal(16)
		self.rxcharisk = Signal(2)

		self.source = Source([("data", 32), ("charisk", 4)])
		###

		# convert data widths
		rx_converter = RenameClockDomains(Converter([("raw", 16+2)], [("raw", 32+4)]), "sata_rx")
		self.submodules += rx_converter
		self.comb += [
			rx_converter.sink.stb.eq(1),
			rx_converter.sink.raw.eq(Cat(self.rxdata , self.rxcharisk)),
			rx_converter.source.ack.eq(1)
		]


		# clock domain crossing
		# SATA device is supposed to lock its tx frequency to its received rx frequency, so this
		# ensure that sata_rx and sata_tx clock have the same frequency with only not the same
		# phase and thus ensute the rx_fifo will never be full.
		rx_fifo = AsyncFIFO([("raw", 36)], 16)
		self.submodules.rx_fifo = RenameClockDomains(rx_fifo, {"write": "sata_rx", "read": "sys"})
		self.comb += [
			rx_converter.source.connect(self.rx_fifo.sink),
			self.rx_fifo.source.ack.eq(1),
		]

		# rearrange data
		self.comb += [
			self.source.stb.eq(self.rx_fifo.source.stb),
			self.source.payload.data.eq(Cat(rx_fifo.source.raw[0:16], rx_fifo.source.raw[18:18+16])),
			self.source.payload.charisk.eq(Cat(rx_fifo.source.raw[16:18], rx_fifo.source.raw[18+16:18+18])),
			self.rx_fifo.source.ack.eq(self.source.ack),
		]

class K7SATAPHYTXConvert(Module):
	def __init__(self):
		self.sink = Sink([("data", 32), ("charisk", 4)])

		self.txdata = Signal(16)
		self.txcharisk = Signal(2)
		###

		# convert data widths
		tx_converter = RenameClockDomains(Converter([("raw", 32+4)], [("raw", 16+2)]), "sata_tx")
		self.submodules += tx_converter
		self.comb += [
			Cat(self.txdata, self.txcharisk).eq(tx_converter.source.raw),
			tx_converter.source.ack.eq(1),
		]

		# clock domain crossing
		tx_fifo = AsyncFIFO([("raw", 36)], 16)
		self.submodules.tx_fifo = RenameClockDomains(tx_fifo, {"write": "sys", "read": "sata_tx"})
		self.comb += [
			tx_fifo.source.connect(tx_converter.sink),
			self.tx_fifo.sink.stb.eq(1),
		]

		# rearrange data
		self.comb += [
			self.tx_fifo.sink.stb.eq(self.sink.stb),
			self.tx_fifo.sink.raw.eq(Cat(self.sink.data[0:16],  self.sink.charisk[0:2],
										 self.sink.data[16:32], self.sink.charisk[2:4])),
			self.sink.ack.eq(self.tx_fifo.sink.ack),
		]
