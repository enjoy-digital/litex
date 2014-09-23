from migen.fhdl.std import *
from lib.sata.k7satagtx import SATAGTX

K28_5 = Signal(8, reset=0xBC)

class K7SATAPHY(Module):
	def __init__(self, pads, dw=16):
		self.sata_gtx = SATAGTX(pads)

		self.sink = Sink([("d", dw)], True)
		self.source = Source([("d", dw)], True)

		rx_chariscomma = self.sata_gtx.channel.rxchariscomma
		rx_chariscomma_d = Signal(dw//8)
		rx_data = self.sata_gtx.channel.rxdata

		tx_charisk = self.sata_gtx.channel.txcharisk
		tx_data = self.sata_gtx.channel.txdata

		# link ready (same chariscomma for N times) #FIXME see how to do it for SATA
		self.link_ready = Signal()
		link_ready_cnt = Signal(8, reset=16-1)
		self.sync.sata_rx += [
			If(rx_chariscomma != 0,
				If(rx_chariscomma == rx_chariscomma_d,
					If(~link_ready, link_ready_cnt.eq(link_ready_cnt-1))
				).Else(
					link_ready_cnt.eq(8-1)
				),
				rx_chariscomma_d.eq(rx_chariscomma)
			)
		]
		self.comb += self.link_ready.eq(link_ready_cnt==0)

		# Send K28_5 on start of frame #FIXME see how to do it for SATA
		self.comb += [
			If(self.sink.sop,
				tx_charisk.eq(1),
				tx_data.eq(Cat(K28_5, self.sink.dat[8:]))
			).Else(
				tx_charisk.eq(0),
				tx_data.eq(self.sink.dat)
			),
			self.sink.ack.eq(1)
		]

		# Realign rx data and drive source #FIXME see how to do it for SATA
		rx_data_r = Signal(dw)
		rx_chariscomma_r = Signal(dw//8)
		rx_data_realigned = Signal(dw)
		rx_chariscomma_realigned = Signal(dw)

		self.sync += [
			rx_data_r.eq(rx_data),
			rx_chariscomma_r.eq(rx_chariscomma)
		]

		cases = {}
		cases[1<<0] = [
				rx_data_realigned.eq(rx_data_r[0:dw]),
				rx_chariscomma_realigned.eq(rx_chariscomma_r[0:dw//8])
		]
		for i in range(1, dw//8):
			cases[1<<i] = [
				rx_data_realigned.eq(Cat(rx_data[8*i:dw], rx_data_r[0:8*i])),
				rx_chariscomma_realigned.eq(Cat(rx_chariscomma[i:dw//8], rx_chariscomma_r[0:i]))
			]
		self.comb += Case(rx_chariscomma_d, cases)

		self.comb += [
			self.source.stb.eq(link_ready),
			self.source.sop.eq(rx_chariscomma_realigned != 0),
			self.source.dat.eq(rx_data_realigned)
		]
