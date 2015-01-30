from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

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

class LiteEthIPTX(Module):
	def __init__(self, mac_address, ip_address, arp_table):
		self.sink = Sink(eth_ipv4_user_description(8))
		self.source = Source(eth_mac_description(8))
		###
		packetizer = LiteEthIPV4Packetizer()
		self.submodules += packetizer
		self.comb += [
			Record.connect(self.sink, packetizer.sink),
			packetizer.sink.version.eq(0x5),
			packetizer.sink.ihl.eq(0x4),
			packetizer.sink.dscp.eq(0),
			packetizer.sink.ecn.eq(0),
			packetizer.sink.identification.eq(0),
			packetizer.sink.flags.eq(0),
			packetizer.sink.fragment_offset.eq(0),
			packetizer.sink.time_to_live.eq(0x80),
			packetizer.sink.source_ip_address.eq(ip_address),
			packetizer.sink.options.eq(0)
		]
		sink = packetizer.source

		destination_mac_address = Signal(48)

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			sink.ack.eq(1),
			If(sink.stb & sink.sop,
				sink.ack.eq(0),
				NextState("SEND_MAC_ADDRESS_REQUEST")
			)
		)
		fsm.act("SEND_MAC_ADDRESS_REQUEST",
			arp_table.request.stb.eq(1),
			arp_table.request.ip_address.eq(self.sink.destination_ip_address),
			If(arp_table.request.stb & arp_table.request.ack,
				NextState("WAIT_MAC_ADDRESS_RESPONSE")
			)
		)
		fsm.act("WAIT_MAC_ADDRESS_RESPONSE",
			# XXX add timeout
			If(arp_table.response.stb,
				arp_table.response.ack.eq(1),
				# XXX manage failed
				NextState("SEND")
			)
		)
		self.sync += If(arp_table.response.stb, destination_mac_address.eq(arp_table.response.mac_address))
		fsm.act("SEND",
			Record.connect(packetizer.source, self.source),
			self.source.ethernet_type.eq(ethernet_type_ip),
			self.source.destination_mac_address.eq(destination_mac_address),
			self.source.source_mac_address.eq(mac_address),
			# XXX compute check sum
			If(self.source.stb & self.source.eop & self.source.ack,
				# XXX manage failed
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
		self.comb += valid.eq(1) # XXX FIXME
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
			source.total_length.eq(sink.total_length),
			source.protocol.eq(sink.protocol),
			source.destination_ip_address.eq(sink.destination_ip_address),
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

class LiteEthIP(Module):
	def __init__(self, mac, mac_address, ip_address, arp_table):
		self.submodules.tx = LiteEthIPTX(mac_address, ip_address, arp_table)
		self.submodules.rx = LiteEthIPRX(mac_address, ip_address)
		mac_port = mac.crossbar.get_port(ethernet_type_ip)
		self.comb += [
			Record.connect(self.tx.source, mac_port.sink),
			Record.connect(mac_port.source, self.rx.sink)
		]
		self.sink, self.source = self.tx.sink, self.rx.source
