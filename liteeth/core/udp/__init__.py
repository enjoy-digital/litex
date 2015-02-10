from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer
from liteeth.generic.crossbar import LiteEthCrossbar
from liteeth.core.udp.common import *

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

class LiteEthUDPCrossbar(LiteEthCrossbar):
	def __init__(self):
		LiteEthCrossbar.__init__(self, LiteEthUDPMasterPort, "dst_port")

	def get_port(self, udp_port, dw=8):
		if udp_port in self.users.keys():
			raise ValueError("Port {0:#x} already assigned".format(udp_port))
		user_port = LiteEthUDPUserPort(dw)
		internal_port = LiteEthUDPUserPort(8)
		if dw != 8:
			converter = Converter(eth_udp_user_description(user_port.dw), eth_udp_user_description(8))
			self.submodules += converter
			self.comb += [
				Record.connect(user_port.sink, converter.sink),
				Record.connect(converter.source, internal_port.sink)
			]
			converter = Converter(eth_udp_user_description(8), eth_udp_user_description(user_port.dw))
			self.submodules += converter
			self.comb += [
				Record.connect(internal_port.source, converter.sink),
				Record.connect(converter.source, user_port.source)
			]
			self.users[udp_port] = internal_port
		else:
			self.users[udp_port] = user_port
		return user_port

class LiteEthUDPTX(Module):
	def __init__(self, ip_address):
		self.sink = sink = Sink(eth_udp_user_description(8))
		self.source = source = Source(eth_ipv4_user_description(8))
		###
		self.submodules.packetizer = packetizer = LiteEthUDPPacketizer()
		self.comb += [
			packetizer.sink.stb.eq(sink.stb),
			packetizer.sink.sop.eq(sink.sop),
			packetizer.sink.eop.eq(sink.eop),
			sink.ack.eq(packetizer.sink.ack),
			packetizer.sink.src_port.eq(sink.src_port),
			packetizer.sink.dst_port.eq(sink.dst_port),
			packetizer.sink.length.eq(sink.length + udp_header_len),
			packetizer.sink.checksum.eq(0), # Disabled (MAC CRC is enough)
			packetizer.sink.data.eq(sink.data)
		]

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
			source.length.eq(packetizer.sink.length),
			source.protocol.eq(udp_protocol),
			source.ip_address.eq(sink.ip_address),
			If(source.stb & source.eop & source.ack,
				NextState("IDLE")
			)
		)

class LiteEthUDPRX(Module):
	def __init__(self, ip_address):
		self.sink = sink = Sink(eth_ipv4_user_description(8))
		self.source = source = Source(eth_udp_user_description(8))
		###
		self.submodules.depacketizer = depacketizer = LiteEthUDPDepacketizer()
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
		self.sync += valid.eq(
			depacketizer.source.stb &
			(sink.protocol == udp_protocol)
		)

		fsm.act("CHECK",
			If(valid,
				NextState("PRESENT")
			).Else(
				NextState("DROP")
			)
		)
		self.comb += [
			source.sop.eq(depacketizer.source.sop),
			source.eop.eq(depacketizer.source.eop),
			source.src_port.eq(depacketizer.source.src_port),
			source.dst_port.eq(depacketizer.source.dst_port),
			source.ip_address.eq(sink.ip_address),
			source.length.eq(depacketizer.source.length - udp_header_len),
			source.data.eq(depacketizer.source.data),
			source.error.eq(depacketizer.source.error)
		]
		fsm.act("PRESENT",
			source.stb.eq(depacketizer.source.stb),
			depacketizer.source.ack.eq(source.ack),
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

class LiteEthUDP(Module):
	def __init__(self, ip, ip_address):
		self.submodules.tx = tx = LiteEthUDPTX(ip_address)
		self.submodules.rx = rx = LiteEthUDPRX(ip_address)
		ip_port = ip.crossbar.get_port(udp_protocol)
		self.comb += [
			Record.connect(tx.source, ip_port.sink),
			Record.connect(ip_port.source, rx.sink)
		]
		self.submodules.crossbar = crossbar = LiteEthUDPCrossbar()
		self.comb += [
			Record.connect(crossbar.master.source, tx.sink),
			Record.connect(rx.source, crossbar.master.sink)
		]
