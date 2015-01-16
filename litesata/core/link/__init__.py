from litesata.common import *
from litesata.core.link.crc import LiteSATACRCInserter, LiteSATACRCChecker
from litesata.core.link.scrambler import LiteSATAScrambler
from litesata.core.link.cont import LiteSATACONTInserter, LiteSATACONTRemover

from_rx = [
	("idle", 1),
	("insert", 32),
	("det", 32)
]

class LiteSATALinkTX(Module):
	def __init__(self, phy):
		self.sink = Sink(link_description(32))
		self.from_rx = Sink(from_rx)

		###

		self.fsm = fsm = FSM(reset_state="IDLE")

		# insert CRC
		crc = LiteSATACRCInserter(link_description(32))
		self.submodules += crc

		# scramble
		scrambler = LiteSATAScrambler(link_description(32))
		self.submodules += scrambler

		# connect CRC / scrambler
		self.comb += [
			Record.connect(self.sink, crc.sink),
			Record.connect(crc.source, scrambler.sink)
		]

		# inserter CONT and scrambled data between
		# CONT and next primitive
		self.cont  = cont = BufferizeEndpoints(LiteSATACONTInserter(phy_description(32)), "source")

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
			scrambler.reset.eq(1),
			If(self.from_rx.idle,
				insert.eq(primitives["SYNC"]),
				If(scrambler.source.stb & scrambler.source.sop,
					If(self.from_rx.det == primitives["SYNC"],
						NextState("RDY")
					)
				)
			)
		)
		fsm.act("RDY",
			insert.eq(primitives["X_RDY"]),
			If(~self.from_rx.idle,
				NextState("IDLE")
			).Elif(self.from_rx.det == primitives["R_RDY"],
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

class LiteSATALinkRX(Module):
	def __init__(self, phy):
		self.source = Source(link_description(32))
		self.to_tx = Source(from_rx)

		###

		self.fsm = fsm = FSM(reset_state="IDLE")

		# CONT remover
		self.cont = cont = BufferizeEndpoints(LiteSATACONTRemover(phy_description(32)), "source")
		self.comb += Record.connect(phy.source, cont.sink)

		# datas / primitives detection
		insert = Signal(32)
		det = Signal(32)
		self.comb += \
			If(cont.source.stb & (cont.source.charisk == 0b0001),
				det.eq(cont.source.data)
			)

		# descrambler
		self.scrambler = scrambler = LiteSATAScrambler(link_description(32))

		# check CRC
		self.crc = crc = LiteSATACRCChecker(link_description(32))

		sop = Signal()
		eop = Signal()
		self.sync += \
			If(fsm.ongoing("IDLE"),
				sop.eq(1),
			).Elif(fsm.ongoing("COPY"),
				If(scrambler.sink.stb & scrambler.sink.ack,
					sop.eq(0)
				)
			)
		self.comb += eop.eq(det == primitives["EOF"])

		crc_error = Signal()
		self.sync += \
			If(crc.source.stb & crc.source.eop & crc.source.ack,
				crc_error.eq(crc.source.error)
			)

		# small fifo to manage HOLD
		self.fifo = SyncFIFO(link_description(32), 32)

		# graph
		self.comb += [
			cont.source.ack.eq(1),
			Record.connect(scrambler.source, crc.sink),
			Record.connect(crc.source, self.fifo.sink),
			Record.connect(self.fifo.source, self.source)
		]
		cont_source_data_d = Signal(32)
		self.sync += \
			If(cont.source.stb & (det == 0),
				scrambler.sink.d.eq(cont.source.data)
			)

		# FSM
		fsm.act("IDLE",
			scrambler.reset.eq(1),
			If(det == primitives["X_RDY"],
				NextState("RDY")
			)
		)
		fsm.act("RDY",
			insert.eq(primitives["R_RDY"]),
			If(det == primitives["SOF"],
				NextState("WAIT_FIRST")
			)
		)
		fsm.act("WAIT_FIRST",
			insert.eq(primitives["R_IP"]),
			If(cont.source.stb & (det == 0),
				NextState("COPY")
			)
		)
		self.comb += [
			scrambler.sink.sop.eq(sop),
			scrambler.sink.eop.eq(eop)
		]
		fsm.act("COPY",
			scrambler.sink.stb.eq(cont.source.stb & ((det == 0) | eop)),
			insert.eq(primitives["R_IP"]),
			If(det == primitives["HOLD"],
				insert.eq(primitives["HOLDA"])
			).Elif(det == primitives["EOF"],
				NextState("WTRM")
			).Elif(self.fifo.fifo.level > 8,
				insert.eq(primitives["HOLD"])
			)
		)
		fsm.act("EOF",
			insert.eq(primitives["R_IP"]),
			If(det == primitives["WTRM"],
				NextState("WTRM")
			)
		)
		fsm.act("WTRM",
			insert.eq(primitives["R_IP"]),
			If(~crc_error,
				NextState("R_OK")
			).Else(
				NextState("R_ERR")
			)
		)
		fsm.act("R_OK",
			insert.eq(primitives["R_OK"]),
			If(det == primitives["SYNC"],
				NextState("IDLE")
			)
		)
		fsm.act("R_ERR",
			insert.eq(primitives["R_ERR"]),
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

class LiteSATALink(Module):
	def __init__(self, phy):
		self.tx = LiteSATALinkTX(phy)
		self.rx = LiteSATALinkRX(phy)
		self.comb += Record.connect(self.rx.to_tx, self.tx.from_rx)
		self.sink, self.source = self.tx.sink, self.rx.source
