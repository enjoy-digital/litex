from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState

from lib.sata.std import *
from lib.sata.link.crc import SATACRCInserter, SATACRCChecker
from lib.sata.link.scrambler import SATAScrambler
from lib.sata.link.cont import SATACONTInserter, SATACONTRemover

# TODO:
# - Do more tests

from_rx = [
	("idle", 1),
	("insert", 32),
	("det", 32)
]

class SATALinkLayerTX(Module):
	def __init__(self, phy):
		self.sink = Sink(link_layout(32))
		self.from_rx = Sink(from_rx)

		###

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		# insert CRC
		crc = SATACRCInserter(link_layout(32))
		self.submodules += crc

		# scramble
		scrambler = SATAScrambler(link_layout(32))
		self.submodules += scrambler

		# connect CRC / scrambler
		self.comb += [
			Record.connect(self.sink, crc.sink),
			Record.connect(crc.source, scrambler.sink)
		]

		# inserter CONT and scrambled data between
		# CONT and next primitive
		cont  = SATACONTInserter(phy_layout(32))
		self.submodules += cont

		# datas / primitives mux
		insert = Signal(32)
		self.comb += [
			If(self.from_rx.insert,
				cont.sink.stb.eq(1),
				cont.sink.data.eq(self.from_rx.insert),
				cont.sink.charisk.eq(0x0001),
			).
			Elif(insert,
				cont.sink.stb.eq(1),
				cont.sink.data.eq(insert),
				cont.sink.charisk.eq(0x0001),
			).Elif(fsm.ongoing("COPY"),
				cont.sink.stb.eq(scrambler.source.stb),
				cont.sink.data.eq(scrambler.source.d),
				scrambler.source.ack.eq(cont.sink.ack),
				cont.sink.charisk.eq(0)
			)
		]
		self.comb += Record.connect(cont.source, phy.sink)

		# FSM
		fsm.act("IDLE",
			insert.eq(primitives["SYNC"]),
			If(scrambler.source.stb & scrambler.source.sop,
				If(self.from_rx.idle,
					NextState("RDY")
				)
			)
		)
		fsm.act("RDY",
			insert.eq(primitives["X_RDY"]),
			If(self.from_rx.det == primitives["R_RDY"],
				NextState("SOF")
			)
		)
		fsm.act("SOF",
			insert.eq(primitives["SOF"]),
			If(phy.sink.ack,
				NextState("COPY")
			)
		)
		fsm.act("COPY",
			If(self.from_rx.det == primitives["HOLD"],
				insert.eq(primitives["HOLDA"]),
			).Elif(~scrambler.source.stb,
				insert.eq(primitives["HOLD"]),
			).Elif(scrambler.source.stb & scrambler.source.eop & scrambler.source.ack,
				NextState("EOF")
			)
		)
		fsm.act("EOF",
			insert.eq(primitives["EOF"]),
			If(phy.sink.ack,
				NextState("WTRM")
			)
		)
		fsm.act("WTRM",
			insert.eq(primitives["WTRM"]),
			If(self.from_rx.det == primitives["R_OK"],
				NextState("IDLE")
			).Elif(self.from_rx.det == primitives["R_ERR"],
				NextState("IDLE")
			)
		)

class SATALinkLayerRX(Module):
	def __init__(self, phy):
		self.source = Source(link_layout(32))
		self.to_tx = Source(from_rx)

		###

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		# CONT remover
		cont = SATACONTRemover(phy_layout(32))
		self.submodules += cont
		self.comb += Record.connect(phy.source, cont.sink)

		# datas / primitives detection
		insert = Signal(32)
		det = Signal(32)
		self.comb += \
			If(cont.source.stb & (cont.source.charisk == 0b0001),
				det.eq(cont.source.data)
			)

		# descrambler
		scrambler = SATAScrambler(link_layout(32))
		self.submodules += scrambler

		# check CRC
		crc = SATACRCChecker(link_layout(32))
		self.submodules += crc

		# graph
		self.comb += [
			If(fsm.ongoing("COPY") & (det == 0),
				scrambler.sink.stb.eq(cont.source.stb & (cont.source.charisk == 0)),
				scrambler.sink.d.eq(cont.source.data),
			),
			cont.source.ack.eq(1),
			Record.connect(scrambler.source, crc.sink),
			Record.connect(crc.source, self.source)
		]

		# FSM
		fsm.act("IDLE",
			If(det == primitives["X_RDY"],
				NextState("RDY")
			)
		)
		fsm.act("RDY",
			insert.eq(primitives["R_RDY"]),
			If(det == primitives["SOF"],
				NextState("COPY")
			)
		)
		fsm.act("COPY",
			If(det == primitives["HOLD"],
				insert.eq(primitives["HOLDA"])
			).Elif(det == primitives["EOF"],
				NextState("WTRM")
			)
		)
		fsm.act("EOF",
			If(det == primitives["WTRM"],
				NextState("WTRM")
			)
		)
		fsm.act("WTRM",
			insert.eq(primitives["R_OK"]),
			If(det == primitives["SYNC"],
				NextState("IDLE")
			)
		)

		# to TX
		self.comb += [
			self.to_tx.idle.eq(fsm.ongoing("IDLE")),
			self.to_tx.insert.eq(insert),
			self.to_tx.det.eq(det)
		]

class SATALinkLayer(Module):
	def __init__(self, phy):
		self.submodules.tx = SATALinkLayerTX(phy)
		self.submodules.rx = SATALinkLayerRX(phy)
		self.comb += Record.connect(self.rx.to_tx, self.tx.from_rx)
		self.sink, self.source = self.tx.sink, self.rx.source
