from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState

from lib.sata.std import *
from lib.sata.link.crc import SATACRCInserter, SATACRCChecker
from lib.sata.link.scrambler import SATAScrambler

# Todo:
# - TX: insert COND and scramble between COND and primitives
# - RX: manage COND

class SATALinkLayer(Module):
	def __init__(self, phy):
		self.sink = Sink(link_layout(32))
		self.source = Source(link_layout(32))

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

	# TX
		# insert CRC
		crc_inserter = SATACRCInserter(link_layout(32))
		self.submodules += crc_inserter

		# scramble
		scrambler = SATAScrambler(link_layout(32))
		self.submodules += scrambler

		# graph
		self.comb += [
			Record.connect(self.sink, crc_inserter.sink),
			Record.connect(crc_inserter.source, scrambler.sink)
		]

		# datas / primitives mux
		tx_insert = Signal(32)
		self.comb += [
			If(tx_insert != 0,
				phy.sink.stb.eq(1),
				phy.sink.data.eq(tx_insert),
				phy.sink.charisk.eq(0x0001),
			).Elif(fsm.ongoing("H2D_COPY"),
				phy.sink.stb.eq(scrambler.source.stb),
				phy.sink.data.eq(scrambler.source.d),
				scrambler.source.ack.eq(phy.source.ack),
				phy.sink.charisk.eq(0)
			)
		]

	# RX
		# datas / primitives detection
		rx_det = Signal(32)
		self.comb += \
			If(phy.source.stb & (phy.source.charisk == 0b0001),
				rx_det.eq(phy.source.data)
			)

		# descrambler
		descrambler = SATAScrambler(link_layout(32))
		self.submodules += descrambler

		# check CRC
		crc_checker = SATACRCChecker(link_layout(32))
		self.submodules += crc_checker

		# graph
		self.comb += [
			If(fsm.ongoing("D2H_COPY") & (rx_det == 0),
				descrambler.sink.stb.eq(phy.source.stb & (phy.source.charisk == 0)),
				descrambler.sink.d.eq(phy.source.data),
			),
			phy.source.ack.eq(1),
			Record.connect(descrambler.source, crc_checker.sink),
			Record.connect(crc_checker.source, self.source)
		]

	# FSM
		fsm.act("IDLE",
			tx_insert.eq(primitives["SYNC"]),
			If(rx_det == primitives["X_RDY"],
				NextState("D2H_RDY")
			).Elif(scrambler.source.stb & scrambler.source.sop,
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
			).Elif(~scrambler.source.stb,
				tx_insert.eq(primitives["HOLD"]),
			).Elif(scrambler.source.stb & scrambler.source.eop & scrambler.source.ack,
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
