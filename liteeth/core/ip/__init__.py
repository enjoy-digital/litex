from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer
from liteeth.core.ip.crossbar import LiteEthIPV4Crossbar

class LiteEthIPV4Depacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_mac_description(8),
			eth_ipv4_description(8),
			ipv4_header,
			ipv4_header_len)

class LiteEthIPV4Packetizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_ipv4_description(8),
			eth_mac_description(8),
			ipv4_header,
			ipv4_header_len)

class LiteEthIPV4Checksum(Module):
	def __init__(self, skip_header=False):
		self.header = Signal(ipv4_header_len*8)
		self.value = Signal(16)

		s = Signal(17)
		r = Signal(17)
		for i in range(ipv4_header_len//2):
			if skip_header and i == 5:
				pass
			else:
				s_next = Signal(17)
				r_next = Signal(17)
				self.comb += [
					s_next.eq(r + self.header[i*16:(i+1)*16]),
					r_next.eq(Cat(s_next[:16]+s_next[16], Signal()))
				]
				s, r = s_next, r_next
		self.comb += self.value.eq(~Cat(r[8:16], r[:8]))

class LiteEthIPTX(Module):
	def __init__(self, mac_address, ip_address, arp_table):
		self.sink = Sink(eth_ipv4_user_description(8))
		self.source = Source(eth_mac_description(8))
		self.target_unreachable = Signal()
		###
		packetizer = LiteEthIPV4Packetizer()
		self.submodules += packetizer
		self.comb += [
			packetizer.sink.stb.eq(self.sink.stb),
			packetizer.sink.sop.eq(self.sink.sop),
			packetizer.sink.eop.eq(self.sink.eop),
			self.sink.ack.eq(packetizer.sink.ack),
			packetizer.sink.target_ip.eq(self.sink.ip_address),
			packetizer.sink.protocol.eq(self.sink.protocol),
			packetizer.sink.total_length.eq(self.sink.length + (0x5*4)),
			packetizer.sink.version.eq(0x4), 	# ipv4
			packetizer.sink.ihl.eq(0x5), 		# 20 bytes
			packetizer.sink.identification.eq(0),
			packetizer.sink.ttl.eq(0x80),
			packetizer.sink.sender_ip.eq(ip_address),
			packetizer.sink.data.eq(self.sink.data)
		]
		sink = packetizer.source

		checksum = LiteEthIPV4Checksum(skip_header=True)
		self.submodules += checksum
		self.comb += [
			checksum.header.eq(packetizer.header),
			packetizer.sink.checksum.eq(checksum.value)
		]

		target_mac = Signal(48)

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			sink.ack.eq(1),
			If(sink.stb & sink.sop,
				sink.ack.eq(0),
				NextState("SEND_MAC_ADDRESS_REQUEST")
			)
		)
		self.comb += arp_table.request.ip_address.eq(self.sink.ip_address)
		fsm.act("SEND_MAC_ADDRESS_REQUEST",
			arp_table.request.stb.eq(1),
			If(arp_table.request.stb & arp_table.request.ack,
				NextState("WAIT_MAC_ADDRESS_RESPONSE")
			)
		)
		fsm.act("WAIT_MAC_ADDRESS_RESPONSE",
			If(arp_table.response.stb,
				arp_table.response.ack.eq(1),
				If(arp_table.response.failed,
					self.target_unreachable.eq(1),
					NextState("DROP"),
				).Else(
					NextState("SEND")
				)
			)
		)
		self.sync += If(arp_table.response.stb, target_mac.eq(arp_table.response.mac_address))
		fsm.act("SEND",
			Record.connect(packetizer.source, self.source),
			self.source.ethernet_type.eq(ethernet_type_ip),
			self.source.target_mac.eq(target_mac),
			self.source.sender_mac.eq(mac_address),
			If(self.source.stb & self.source.eop & self.source.ack,
				NextState("IDLE")
			)
		)
		fsm.act("DROP",
			packetizer.source.ack.eq(1),
			If(packetizer.source.stb & packetizer.source.eop & packetizer.source.ack,
				NextState("IDLE")
			)
		)

class LiteEthIPRX(Module):
	def __init__(self, mac_address, ip_address):
		self.sink = Sink(eth_mac_description(8))
		self.source = source = Source(eth_ipv4_user_description(8))
		###
		depacketizer = LiteEthIPV4Depacketizer()
		self.submodules += depacketizer
		self.comb += Record.connect(self.sink, depacketizer.sink)
		sink = depacketizer.source

		checksum = LiteEthIPV4Checksum(skip_header=False)
		self.submodules += checksum
		self.comb += checksum.header.eq(depacketizer.header)

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
			(sink.target_ip == ip_address) &
			(sink.version == 0x4) &
			(sink.ihl == 0x5) &
			(checksum.value == 0)
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
			source.length.eq(sink.total_length - (sink.ihl*4)),
			source.protocol.eq(sink.protocol),
			source.ip_address.eq(sink.target_ip),
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

class LiteEthIP(Module):
	def __init__(self, mac, mac_address, ip_address, arp_table):
		self.submodules.tx = LiteEthIPTX(mac_address, ip_address, arp_table)
		self.submodules.rx = LiteEthIPRX(mac_address, ip_address)
		mac_port = mac.crossbar.get_port(ethernet_type_ip)
		self.comb += [
			Record.connect(self.tx.source, mac_port.sink),
			Record.connect(mac_port.source, self.rx.sink)
		]
		self.submodules.crossbar = LiteEthIPV4Crossbar()
		self.comb += [
			Record.connect(self.crossbar.master.source, self.tx.sink),
			Record.connect(self.rx.source, self.crossbar.master.sink)
		]
