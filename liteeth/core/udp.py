from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

class LiteEthUDPDepacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_ipv4_user_description(8),
			eth_udp_description(8),
			udp_header,
			udp_header_len)

class LiteEthUDPPacketizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_udp_description(8),
			eth_ipv4_user_description(8),
			udp_header,
			udp_header_len)

class LiteEthUDPTX(Module):
	def __init__(self, ip_address):
		self.sink = Sink(eth_udp_user_description(8))
		self.source = Source(eth_ipv4_user_description(8))
		###
		packetizer = LiteEthUDPV4Packetizer()
		self.submodules += packetizer
		self.comb += [
			packetizer.sink.stb.eq(self.sink.stb),
			packetizer.sink.sop.eq(self.sink.sop),
			packetizer.sink.eop.eq(self.sink.eop),
			self.sink.eq(packetizer.sink.ack),
			packetizer.sink.source_port.eq(self.sink.source_port),
			packetizer.sink.destination_port.eq(self.sink.destination_port),
			packetizer.sink.length.eq(self.sink.length + udp_header_len),
			packetizer.sink.checksum.eq(0),
		]
		sink = packetizer.source

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			sink.ack.eq(1),
			If(sink.stb & sink.sop,
				sink.ack.eq(0),
				NextState("SEND")
			)
		)
		fsm.act("SEND",
			Record.connect(packetizer.source, self.source),
			self.source.length.eq(),
			self.source.protocol.eq(udp_protocol),
			self.source.ip_address.eq(self.sink.ip_address),
			If(self.source.stb & self.source.eop & self.source.ack,
				NextState("IDLE")
			)
		)

class LiteEthUDPRX(Module):
	def __init__(self, ip_address):
		self.sink = Sink(eth_ipv4_user_description(8))
		self.source = source = Source(eth_udp_user_description(8))
		###
		depacketizer = LiteEthUDPV4Depacketizer()
		self.submodules += depacketizer
		self.comb += Record.connect(self.sink, depacketizer.sink)
		sink = depacketizer.source

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			sink.ack.eq(1),
			If(sink.stb & sink.sop,
				sink.ack.eq(0),
				NextState("CHECK")
			)
		)
		valid = Signal()
		self.comb += valid.eq(
			sink.stb &
			(sink.protocol == udp_protocol) &
			(sink.ip_address == ip_address)
		)

		fsm.act("CHECK",
			If(valid,
				NextState("PRESENT")
			).Else(
				NextState("DROP")
			)
		),
		fsm.act("PRESENT",
			source.stb.eq(sink.stb),
			source.sop.eq(sink.sop),
			source.eop.eq(sink.eop),
			sink.ack.eq(source.ack),
			source.source_port.eq(sink.source_port),
			source.destination_port.eq(sink.destination_port),
			source.ip_address.eq(0),
			source.length.eq(sink.length - udp_header_len),
			source.data.eq(sink.data),
			source.error.eq(sink.error),
			If(source.stb & source.eop & source.ack,
				NextState("IDLE")
			)
		)
		fsm.act("DROP",
			sink.ack.eq(1),
			If(source.stb & source.eop & source.ack,
				NextState("IDLE")
			)
		)

class LiteEthUDP(Module):
	def __init__(self, ip_address):
		self.submodules.tx = LiteEthUDPTX(ip_address)
		self.submodules.rx = LiteEthUDPRX(ip_address)
		self.sink, self.source = self.tx.sink, self.rx.source
