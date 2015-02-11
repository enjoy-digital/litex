from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

class LiteEthEtherboneRecordPacketizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_etherbone_record_description(32),
			eth_raw_description(32),
			etherbone_record_header,
			etherbone_record_header_len)

class LiteEthEtherboneRecordTX(Module):
	def __init__(self):
		self.sink = sink = Sink(eth_etherbone_record_description(32))
		self.source = source = Source(eth_raw_description(32))
		###
		self.submodules.packetizer = packetizer = LiteEthEtherboneRecordPacketizer()
		self.comb += Record.connect(sink, packetizer.sink)

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			packetizer.source.ack.eq(1),
			If(packetizer.source.stb & packetizer.source.sop,
				packetizer.source.ack.eq(0),
				NextState("SEND")
			)
		)
		fsm.act("SEND",
			Record.connect(packetizer.source, source),
			If(source.stb & source.eop & source.ack,
				NextState("IDLE")
			)
		)

class LiteEthEtherboneRecordDepacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_raw_description(32),
			eth_etherbone_record_description(32),
			etherbone_record_header,
			etherbone_record_header_len)

class LiteEthEtherboneRecordRX(Module):
	def __init__(self):
		self.sink = sink = Sink(eth_raw_description(32))
		self.source = source = Source(eth_etherbone_record_description(32))
		###
		self.submodules.depacketizer = depacketizer = LiteEthEtherboneRecordDepacketizer()
		self.comb += Record.connect(sink, depacketizer.sink)

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			depacketizer.source.ack.eq(1),
			If(depacketizer.source.stb & depacketizer.source.sop,
				depacketizer.source.ack.eq(0),
				NextState("CHECK")
			)
		)
		valid = Signal()
		self.sync += valid.eq(1) # XXX
		fsm.act("CHECK",
			If(valid,
				NextState("PRESENT")
			).Else(
				NextState("DROP")
			)
		)
		fsm.act("PRESENT",
			Record.connect(depacketizer.source, source),
			If(source.stb & source.eop & source.ack,
				NextState("IDLE")
			)
		)
		fsm.act("DROP",
			depacketizer.source.ack.eq(1),
			If(depacketizer.source.stb & depacketizer.source.eop & depacketizer.source.ack,
				NextState("IDLE")
			)
		)

class LiteEthEtherboneRecord(Module):
	def __init__(self):
		self.sink = sink = Sink(eth_etherbone_packet_user_description(32))
		self.source = source = Sink(eth_etherbone_packet_user_description(32))
		###
		self.submodules.record_tx = record_tx = LiteEthEtherboneRecordTX()
		self.submodules.record_rx = record_rx = LiteEthEtherboneRecordRX()
