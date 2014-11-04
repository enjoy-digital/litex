from migen.fhdl.std import *

from lib.sata.std import *
from lib.sata.link import crc
from lib.sata.link import scrambler

class SATALinkLayerTX(Module):
	def __init__(self, dw):
		self.sink = Sink(link_layout(dw))
		self.source = Source(phy_layout(dw))

		###

	# insert CRC
		crc_inserter = crc.SATACRCInserter(link_layout(dw))
		self.submodules += crc_inserter

	# scramble
		scrambler = scrambler.SATAScrambler(link_layout(dw))
		self.submodules += scrambler

class SATALinkLayerRX(Module):
	def __init__(self, dw):
		self.sink = Sink(link_layout(dw))
		self.source = Source(phy_layout(dw))

		###

	# descramble
		descrambler = descrambler.SATAScrambler(link_layout(dw))
		self.submodules += descrambler

	# check CRC
		crc_checker = crc.SATACRCChecker(link_layout(dw))
		self.submodules += crc_checker

class SATALinkLayer(Module):
	def __init__(self, phy, dw=32):
		self.submodules.tx = SATALinkLayerTX(dw)
		self.submodules.rx = SATALinkLayerRX(dw)

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			phy.sink.stb.eq(1),
			phy.sink.d.eq(SYNC_VAL),
			NextState("RDY")
		)
		fsm.act("RDY",
			phy.sink.stb.eq(1),
			phy.sink.d.eq(X_RDY_VAL)
			If(phy.source.stb & (phy.source.d == X_RDY_VAL),
				NextState("SOF")
		)
		fsm.act("SOF",
			phy.sink.stb.eq(1),
			phy.sink.d.eq(SOF_VAL),
			NextState("COPY")
		)
		fsm.act("COPY",
			phy.sink.stb.eq(1),
			phy.sink.d.eq(),
			NextState("EOF")
		)
		fsm.act("EOF",
			phy.sink.stb.eq(1),
			phy.sink.d.eq(EOF_VAL),
			NextState("")
		)
		fsm.act("EOF",
			phy.sink.stb.eq(1),
			phy.sink.d.eq(EOF_VAL),
			NextState("")
		)
		fsm.act("WTRM",
			phy.sink.stb.eq(1),
			phy.sink.d.eq(WTRM_VAL),
			If(phy.source.stb & (phy.source.d == R_OK_VAL),
				NextState("IDLE")
			).Elif(phy.source.stb & (phy.source.d == R_ERR_VAL),
				NextState("IDLE")
			)
		)
