from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState

from lib.sata.std import *
from lib.sata.link.crc import SATACRCInserter, SATACRCChecker
from lib.sata.link.scrambler import SATAScrambler
from lib.sata.link.cont import SATACONTInserter, SATACONTRemover

# TODO:
# - Test D2H
# - Do more tests

class SATALinkLayer(Module):
	def __init__(self, phy):
		self.sink = Sink(link_layout(32))
		self.source = Source(link_layout(32))

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

	# TX
		# insert CRC
		tx_crc = SATACRCInserter(link_layout(32))
		self.submodules += tx_crc

		# scramble
		tx_scrambler = SATAScrambler(link_layout(32))
		self.submodules += tx_scrambler

		# graph
		self.comb += [
			Record.connect(self.sink, tx_crc.sink),
			Record.connect(tx_crc.source, tx_scrambler.sink)
		]

		# inserter CONT and scrambled data between
		# CONT and next primitive
		tx_cont  = SATACONTInserter(phy_layout(32))
		self.submodules += tx_cont

		# datas / primitives mux
		tx_insert = Signal(32)
		self.comb += [
			If(tx_insert != 0,
				tx_cont.sink.stb.eq(1),
				tx_cont.sink.data.eq(tx_insert),
				tx_cont.sink.charisk.eq(0x0001),
			).Elif(fsm.ongoing("H2D_COPY"),
				tx_cont.sink.stb.eq(tx_scrambler.source.stb),
				tx_cont.sink.data.eq(tx_scrambler.source.d),
				tx_scrambler.source.ack.eq(tx_cont.sink.ack),
				tx_cont.sink.charisk.eq(0)
			)
		]

		# graph
		self.comb += Record.connect(tx_cont.source, phy.sink)

	# RX

		# CONT remover
		rx_cont = SATACONTRemover(phy_layout(32))
		self.submodules += rx_cont

		# graph
		self.comb += Record.connect(phy.source, rx_cont.sink)

		# datas / primitives detection
		rx_det = Signal(32)
		self.comb += \
			If(rx_cont.source.stb & (rx_cont.source.charisk == 0b0001),
				rx_det.eq(rx_cont.source.data)
			)

		# descrambler
		rx_scrambler = SATAScrambler(link_layout(32))
		self.submodules += rx_scrambler

		# check CRC
		rx_crc = SATACRCChecker(link_layout(32))
		self.submodules += rx_crc

		# graph
		self.comb += [
			If(fsm.ongoing("D2H_COPY") & (rx_det == 0),
				rx_scrambler.sink.stb.eq(rx_cont.source.stb & (rx_cont.source.charisk == 0)),
				rx_scrambler.sink.d.eq(rx_cont.source.data),
			),
			rx_cont.source.ack.eq(1),
			Record.connect(rx_scrambler.source, rx_crc.sink),
			Record.connect(rx_crc.source, self.source)
		]

	# FSM
		fsm.act("IDLE",
			tx_insert.eq(primitives["SYNC"]),
			If(rx_det == primitives["X_RDY"],
				NextState("D2H_RDY")
			).Elif(tx_scrambler.source.stb & tx_scrambler.source.sop,
				NextState("H2D_RDY")
			)
		)

		# Host to Device
		fsm.act("H2D_RDY",
			tx_insert.eq(primitives["X_RDY"]),
			If(rx_det == primitives["R_RDY"],
				NextState("H2D_SOF")
			)
		)
		fsm.act("H2D_SOF",
			tx_insert.eq(primitives["SOF"]),
			If(phy.sink.ack,
				NextState("H2D_COPY")
			)
		)
		fsm.act("H2D_COPY",
			If(rx_det == primitives["HOLD"],
				tx_insert.eq(primitives["HOLDA"]),
			).Elif(~tx_scrambler.source.stb,
				tx_insert.eq(primitives["HOLD"]),
			).Elif(tx_scrambler.source.stb & tx_scrambler.source.eop & tx_scrambler.source.ack,
				NextState("H2D_EOF")
			)
		)
		fsm.act("H2D_EOF",
			tx_insert.eq(primitives["EOF"]),
			If(phy.sink.ack,
				NextState("H2D_WTRM")
			)
		)
		fsm.act("H2D_WTRM",
			tx_insert.eq(primitives["WTRM"]),
			If(rx_det == primitives["R_OK"],
				NextState("IDLE")
			).Elif(rx_det == primitives["R_ERR"],
				NextState("IDLE")
			)
		)

		# Device to Host
		fsm.act("D2H_RDY",
			tx_insert.eq(primitives["R_RDY"]),
			If(rx_det == primitives["SOF"],
				NextState("D2H_COPY")
			)
		)
		fsm.act("D2H_COPY",
			If(rx_det == primitives["HOLD"],
				tx_insert.eq(primitives["HOLDA"])
			).Elif(rx_det == primitives["EOF"],
				NextState("D2H_WTRM")
			)
		)
		fsm.act("D2H_EOF",
			If(rx_det == primitives["WTRM"],
				NextState("D2H_WTRM")
			)
		)
		fsm.act("D2H_WTRM",
			tx_insert.eq(primitives["R_OK"]),
			If(rx_det == primitives["SYNC"],
				NextState("IDLE")
			)
		)
