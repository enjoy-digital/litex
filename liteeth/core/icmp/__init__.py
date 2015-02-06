from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

class LiteEthICMPDepacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_ipv4_user_description(8),
			eth_icmp_description(8),
			icmp_header,
			icmp_header_len)

class LiteEthICMPPacketizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_icmp_description(8),
			eth_ipv4_user_description(8),
			icmp_header,
			icmp_header_len)

class LiteEthICMPTX(Module):
	def __init__(self, ip_address):
		self.sink = Sink(eth_icmp_user_description(8))
		self.source = Source(eth_ipv4_user_description(8))
		###
		packetizer = LiteEthICMPPacketizer()
		self.submodules += packetizer
		self.comb += [
			packetizer.sink.stb.eq(self.sink.stb),
			packetizer.sink.sop.eq(self.sink.sop),
			packetizer.sink.eop.eq(self.sink.eop),
			self.sink.ack.eq(packetizer.sink.ack),
			packetizer.sink.msgtype.eq(self.sink.msgtype),
			packetizer.sink.code.eq(self.sink.code),
			packetizer.sink.checksum.eq(self.sink.checksum),
			packetizer.sink.quench.eq(self.sink.quench),
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
			self.source.length.eq(self.sink.length + icmp_header_len),
			self.source.protocol.eq(icmp_protocol),
			self.source.ip_address.eq(self.sink.ip_address),
			If(self.source.stb & self.source.eop & self.source.ack,
				NextState("IDLE")
			)
		)

class LiteEthICMPRX(Module):
	def __init__(self, ip_address):
		self.sink = Sink(eth_ipv4_user_description(8))
		self.source = source = Source(eth_icmp_user_description(8))
		###
		depacketizer = LiteEthICMPDepacketizer()
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
			(self.sink.protocol == icmp_protocol)
		)
		fsm.act("CHECK",
			If(valid,
				NextState("PRESENT")
			).Else(
				NextState("DROP")
			)
		)
		self.comb += [
			source.sop.eq(sink.sop),
			source.eop.eq(sink.eop),
			source.msgtype.eq(sink.msgtype),
			source.code.eq(sink.code),
			source.checksum.eq(sink.checksum),
			source.quench.eq(sink.quench),
			source.ip_address.eq(self.sink.ip_address),
			source.length.eq(self.sink.length - icmp_header_len),
			source.data.eq(sink.data),
			source.error.eq(sink.error)
		]
		fsm.act("PRESENT",
			source.stb.eq(sink.stb),
			sink.ack.eq(source.ack),
			If(source.stb & source.eop & source.ack,
				NextState("IDLE")
			)
		)
		fsm.act("DROP",
			sink.ack.eq(1),
			If(sink.stb & sink.eop & sink.ack,
				NextState("IDLE")
			)
		)

class LiteEthICMPEcho(Module):
	def __init__(self):
		self.sink = Sink(eth_icmp_user_description(8))
		self.source = Source(eth_icmp_user_description(8))
		###
		self.submodules.fifo = SyncFIFO(eth_icmp_user_description(8), 512, buffered=True)
		self.comb += [
			Record.connect(self.sink, self.fifo.sink),
			Record.connect(self.fifo.source, self.source),
			self.source.msgtype.eq(0x0),
			self.source.checksum.eq(~((~self.fifo.source.checksum)-0x0800))
		]

class LiteEthICMP(Module):
	def __init__(self, ip, ip_address):
		self.submodules.tx = LiteEthICMPTX(ip_address)
		self.submodules.rx = LiteEthICMPRX(ip_address)
		self.submodules.echo = LiteEthICMPEcho()
		self.comb += [
			Record.connect(self.rx.source, self.echo.sink),
			Record.connect(self.echo.source, self.tx.sink)
		]
		ip_port = ip.crossbar.get_port(icmp_protocol)
		self.comb += [
			Record.connect(self.tx.source, ip_port.sink),
			Record.connect(ip_port.source, self.rx.sink)
		]
