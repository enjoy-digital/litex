from lib.sata.common import *

from migen.genlib.misc import chooser
from migen.flow.plumbing import Multiplexer, Demultiplexer
from migen.actorlib.structuring import Converter

class SATAPHYDatapathRX(Module):
	def __init__(self):
		self.sink = Sink(phy_description(16))
		self.source = Source(phy_description(32))

		###

	# width convertion (16 to 32) and byte alignment
		byte_alignment = Signal()
		last_charisk = Signal(2)
		last_data = Signal(16)
		self.sync.sata_rx += \
			If(self.sink.stb & self.sink.ack,
				If(self.sink.charisk != 0,
					byte_alignment.eq(self.sink.charisk[1])
				),
				last_charisk.eq(self.sink.charisk),
				last_data.eq(self.sink.data)
			)
		converter = Converter(phy_description(16), phy_description(32), reverse=False)
		self.converter = InsertReset(RenameClockDomains(converter, "sata_rx"))
		self.comb += [
			self.converter.sink.stb.eq(self.sink.stb),
			If(byte_alignment,
				self.converter.sink.charisk.eq(Cat(last_charisk[1], self.sink.charisk[0])),
				self.converter.sink.data.eq(Cat(last_data[8:], self.sink.data[:8]))
			).Else(
				self.converter.sink.charisk.eq(self.sink.charisk),
				self.converter.sink.data.eq(self.sink.data)
			),
			self.sink.ack.eq(self.converter.sink.ack),
			self.converter.reset.eq(self.converter.source.charisk[2:] != 0)
		]

	# clock domain crossing
		# (SATA3) 300MHz sata_rx clk to sys_clk
		# (SATA2) 150MHz sata_rx clk to sys_clk
		# (SATA1) 75MHz sata_rx clk to sys_clk
		# requirements:
		# due to the convertion ratio of 2, sys_clk need to be > sata_rx/2
		# source destination is always able to accept data (ack always 1)
		fifo = AsyncFIFO(phy_description(32), 4)
		self.fifo = RenameClockDomains(fifo, {"write": "sata_rx", "read": "sys"})
		self.comb += [
			Record.connect(self.converter.source, fifo.sink),
			Record.connect(fifo.source, self.source)
		]

class SATAPHYDatapathTX(Module):
	def __init__(self):
		self.sink = Sink(phy_description(32))
		self.source = Source(phy_description(16))

		###

	# clock domain crossing
		# (SATA3) sys_clk to 300MHz sata_tx clk
		# (SATA2) sys_clk to 150MHz sata_tx clk
		# (SATA1) sys_clk to 75MHz sata_tx clk
		# requirements:
		# source destination is always able to accept data (ack always 1)
		fifo = AsyncFIFO(phy_description(32), 4)
		self.fifo = RenameClockDomains(fifo, {"write": "sys", "read": "sata_tx"})
		self.comb += Record.connect(self.sink, fifo.sink)

	# width convertion (32 to 16)
		converter = Converter(phy_description(32), phy_description(16), reverse=False)
		self.converter =  RenameClockDomains(converter, "sata_tx")
		self.comb += [
			Record.connect(self.fifo.source, self.converter.sink),
			Record.connect(self.converter.source, self.source)
		]

class SATAPHYAlignInserter(Module):
	def __init__(self, ctrl):
		self.sink = sink = Sink(phy_description(32))
		self.source = source = Source(phy_description(32))

		###

		# send 2 ALIGN every 256 DWORDs
		# used for clock compensation between
		# HOST and device
		cnt = Signal(8)
		send = Signal()
		self.sync += \
			If(~ctrl.ready,
				cnt.eq(0)
			).Elif(source.stb & source.ack,
				cnt.eq(cnt+1)
			)
		self.comb += [
			send.eq(cnt < 2),
			If(send,
				source.stb.eq(1),
				source.charisk.eq(0b0001),
				source.data.eq(primitives["ALIGN"]),
				sink.ack.eq(0)
			).Else(
				source.stb.eq(sink.stb),
				source.data.eq(sink.data),
				source.charisk.eq(sink.charisk),
				sink.ack.eq(source.ack)
			)
		]

class SATAPHYAlignRemover(Module):
	def __init__(self):
		self.sink = sink = Sink(phy_description(32))
		self.source = source = Source(phy_description(32))

		###

		charisk_match = sink.charisk == 0b0001
		data_match = sink.data == primitives["ALIGN"]

		self.comb += \
			If(sink.stb & charisk_match & data_match,
				sink.ack.eq(1),
			).Else(
				Record.connect(sink, source)
			)

class SATAPHYDatapath(Module):
	def __init__(self, trx, ctrl):
		self.sink = Sink(phy_description(32))
		self.source = Source(phy_description(32))

		###

	# TX path
		self.align_inserter = SATAPHYAlignInserter(ctrl)
		self.mux = Multiplexer(phy_description(32), 2)
		self.tx = SATAPHYDatapathTX()
		self.comb += [
			self.mux.sel.eq(ctrl.ready),
			Record.connect(self.sink, self.align_inserter.sink),
			Record.connect(ctrl.source, self.mux.sink0),
			Record.connect(self.align_inserter.source, self.mux.sink1),
			Record.connect(self.mux.source, self.tx.sink),
			Record.connect(self.tx.source, trx.sink)
		]

	# RX path
		self.rx = SATAPHYDatapathRX()
		self.demux = Demultiplexer(phy_description(32), 2)
		self.align_remover = SATAPHYAlignRemover()
		self.comb += [
			self.demux.sel.eq(ctrl.ready),
			Record.connect(trx.source, self.rx.sink),
			Record.connect(self.rx.source, self.demux.sink),
			Record.connect(self.demux.source0, ctrl.sink),
			Record.connect(self.demux.source1, self.align_remover.sink),
			Record.connect(self.align_remover.source, self.source)
		]
