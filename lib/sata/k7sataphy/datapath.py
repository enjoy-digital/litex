from migen.fhdl.std import *
from migen.actorlib.fifo import AsyncFIFO
from migen.actorlib.structuring import Converter
from migen.flow.actor import Sink, Source

from lib.sata.k7sataphy.std import *

class K7SATAPHYRXConvert(Module):
	def __init__(self, dw=16):
		self.rxdata = Signal(dw)
		self.rxcharisk = Signal(dw//8)

		self.source = Source([("data", 32), ("charisk", 4)])

		###

		# byte alignment
		rxdata_r = Signal(2*dw)
		rxcharisk_r = Signal((2*dw)//8)
		rxalignment = Signal(dw//8)
		rxvalid = Signal()
		self.sync.sata_rx += [
			rxdata_r.eq(Cat(self.rxdata, rxdata_r[0:dw])),
			rxcharisk_r.eq(Cat(self.rxcharisk, rxcharisk_r[0:dw//8])),
			If(self.rxcharisk != 0,
				rxalignment.eq(self.rxcharisk),
				rxvalid.eq(1)
			).Else(
				rxvalid.eq(~rxvalid)
			)
		]

		rxdata = Signal(2*dw)
		rxcharisk = Signal((2*dw)//8)
		cases = {}
		cases[1<<0] = [
				rxdata.eq(rxdata_r[0:]),
				rxcharisk.eq(rxcharisk_r[0:])
		]
		for i in range(1, dw//8):
			cases[1<<i] = [
				rxdata.eq(Cat(self.rxdata[8*i:dw], rxdata_r[0:dw+8*i])),
				rxcharisk.eq(Cat(self.rxcharisk[i:dw//8], rxcharisk_r[0:dw//8+i]))
			]
		self.comb += Case(rxalignment, cases)

		# clock domain crossing
		rx_fifo = AsyncFIFO([("data", 32), ("charisk", 4)], 16)
		self.submodules.rx_fifo = RenameClockDomains(rx_fifo, {"write": "sata_rx", "read": "sys"})
		self.comb += [
			rx_fifo.sink.stb.eq(rxvalid),
			rx_fifo.sink.data.eq(rxdata),
			rx_fifo.sink.charisk.eq(rxcharisk),
		]

		# connect source
		self.comb += [
			Record.connect(rx_fifo.source, self.source)
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
