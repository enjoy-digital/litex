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
		packetizer = LiteEthUDPPacketizer()
		self.submodules += packetizer
		self.comb += [
			packetizer.sink.stb.eq(self.sink.stb),
			packetizer.sink.sop.eq(self.sink.sop),
			packetizer.sink.eop.eq(self.sink.eop),
			self.sink.ack.eq(packetizer.sink.ack),
			packetizer.sink.src_port.eq(self.sink.src_port),
			packetizer.sink.dst_port.eq(self.sink.dst_port),
			packetizer.sink.length.eq(self.sink.length + udp_header_len),
			packetizer.sink.checksum.eq(0),
			packetizer.sink.data.eq(self.sink.data)
		]
		sink = packetizer.source

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			sink.ack.eq(1),
			If(sink.stb & sink.sop,
				sink.ack.eq(0),
				NextState("SEND")
			)
		)
		fsm.act("SEND",
			Record.connect(packetizer.source, self.source),
			self.source.length.eq(packetizer.sink.length + ipv4_header_len),
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
		depacketizer = LiteEthUDPDepacketizer()
		self.submodules += depacketizer
		self.comb += Record.connect(self.sink, depacketizer.sink)
		sink = depacketizer.source

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
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
			(self.sink.protocol == udp_protocol) &
			(self.sink.ip_address == ip_address)
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
			source.src_port.eq(sink.src_port),
			source.dst_port.eq(sink.dst_port),
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
	def __init__(self, ip, ip_address):
		self.submodules.tx = LiteEthUDPTX(ip_address)
		self.submodules.rx = LiteEthUDPRX(ip_address)
		self.comb += [
			Record.connect(self.tx.source, ip.sink),
			Record.connect(ip.source, self.rx.sink)
		]
		self.sink, self.source = self.tx.sink, self.rx.source
