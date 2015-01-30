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
	def __init__(self, ip_address, arp_table):
		self.sink = sink = Sink(eth_ipv4_description(8))
		self.source = Source(eth_mac_description(8))
		###
		packetizer = LiteEthIPV4Packetizer()
		self.submodules += packetizer
		source = packetizer.sink

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
			arp_table.request.ip_address.eq(sink.destination_ip_address),
			If(arp_table.request.stb & arp_table.request.ack,
				NextState("WAIT_MAC_ADDRESS_RESPONSE")
			)
		)
		fsm.act("WAIT_MAC_ADDRESS_RESPONSE",
			# XXX add timeout
			If(arp_table.response.stb,
				# XXX manage failed
				NextState("SEND")
			)
		)
		fsm.act("SEND",
			Record.connect(packetizer.source, self.source),
			# XXX compute check sum

			# XXX add timeout
			If(arp_table.response.stb,
				# XXX manage failed
				NextState("SEND")
			)
		)

class LiteEthIPRX(Module):
	def __init__(self, ip_address):
		self.sink = Sink(eth_mac_description(8))
		self.source = source = Source(eth_ipv4_description(8))
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
			Record.connect(sink, source),
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
	def __init__(self, ip_address, arp_table):
		self.submodules.tx = LiteEthIPTX(ip_address, arp_table)
		self.submodules.rx = LiteEthIPRX(ip_address)
		self.sink, self.source = self.rx.sink, self.tx.source
