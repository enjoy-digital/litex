from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

def _arp_table_description():
	layout = [
		("reply", 1),
		("request", 1),
		("ip_address", 32),
		("mac_address", 48)
	]
	return EndpointDescription(layout, packetized=False)

class LiteEthARPDepacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_mac_description(8),
			eth_arp_description(8),
			arp_header,
			arp_header_len)

class LiteEthARPPacketizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_arp_description(8),
			eth_mac_description(8),
			arp_header,
			arp_header_len)

class LiteSATACommandTX(Module):
	def __init__(self, transport):
		self.sink = sink = Sink(command_tx_description(32))


class LiteEthARPTX(Module):
	def __init__(self, mac_address, ip_address):
		self.sink = sink = Sink(_arp_table_description())
		self.source = Source(eth_mac_description(8))
		###
		packetizer = LiteEthARPPacketizer()
		self.submodules += packetizer
		source = packetizer.sink

		counter = Counter(max=arp_packet_length)
		self.submodules += counter

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			sink.ack.eq(1),
			counter.reset.eq(1),
			If(sink.stb,
				sink.ack.eq(0),
				NextState("SEND")
			)
		)
		self.comb += [
			source.hardware_type.eq(arp_hwtype_ethernet),
			source.protocol_type.eq(arp_proto_ip),
			source.hardware_address_length.eq(6),
			source.protocol_address_length.eq(4),
			source.source_mac_address.eq(mac_address),
			source.source_ip_address.eq(ip_address),
			If(sink.reply,
				source.operation.eq(arp_opcode_reply),
				source.destination_mac_address.eq(sink.mac_address),
				source.destination_ip_address.eq(sink.ip_address)
			).Elif(sink.request,
				source.operation.eq(arp_opcode_request),
				source.destination_mac_address.eq(0xffffffffffff),
				source.destination_ip_address.eq(sink.ip_address)
			)
		]
		fsm.act("SEND",
			source.stb.eq(1),
			source.sop.eq(counter.value == 0),
			source.eop.eq(counter.value == arp_packet_length-1),
			Record.connect(packetizer.source, self.source),
			self.source.destination_mac_address.eq(source.destination_mac_address),
			self.source.source_mac_address.eq(mac_address),
			self.source.ethernet_type.eq(ethernet_type_arp),
			If(self.source.stb & self.source.ack,
				sink.ack.eq(1),
				counter.ce.eq(1),
				If(self.source.eop,
					NextState("IDLE")
				)
			)
		)

class LiteEthARPRX(Module):
	def __init__(self, mac_address, ip_address):
		self.sink = Sink(eth_mac_description(8))
		self.source = source = Source(_arp_table_description())
		###
		depacketizer = LiteEthARPDepacketizer()
		self.submodules += depacketizer
		self.comb += Record.connect(self.sink, depacketizer.sink)
		sink = depacketizer.source

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			sink.ack.eq(1),
			If(sink.stb & sink.sop,
				NextState("CHECK")
			)
		)
		valid = Signal()
		self.comb += valid.eq(
			sink.stb &
			(sink.hardware_type == arp_hwtype_ethernet) &
			(sink.protocol_type == arp_proto_ip) &
			(sink.hardware_address_length == 6) &
			(sink.protocol_address_length == 4) &
			(sink.destination_ip_address == ip_address)
		)
		reply = Signal()
		request = Signal()
		self.comb += Case(sink.operation, {
			arp_opcode_request	:	[request.eq(1)],
			arp_opcode_reply	:	[reply.eq(1)],
			"default"			:	[]
			})
		self.comb += [
			source.ip_address.eq(sink.source_ip_address),
			source.mac_address.eq(sink.source_mac_address)
		]
		fsm.act("CHECK",
			If(valid,
				source.stb.eq(1),
				source.reply.eq(reply),
				source.request.eq(request)
			),
			NextState("TERMINATE")
		),
		fsm.act("TERMINATE",
			sink.ack.eq(1),
			If(sink.stb & sink.eop,
				NextState("IDLE")
			)
		)

arp_table_request_layout = [
	("ip_address", 32)
]

arp_table_response_layout = [
	("failed", 1),
	("mac_address", 48)

]

class LiteEthARPTable(Module):
	def __init__(self):
		self.sink = sink = Sink(_arp_table_description()) 		# from arp_rx
		self.source = source = Source(_arp_table_description()) 	# to arp_tx

		# Request/Response interface
		self.request = request = Sink(arp_table_request_layout)
		self.response = response = Source(arp_table_response_layout)

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			If(sink.stb & sink.request,
				NextState("SEND_REPLY")
			).Elif(sink.stb & sink.reply,
				NextState("UPDATE_TABLE")
			).Elif(request.stb,
				NextState("CHECK_TABLE")
			)
		)
		fsm.act("SEND_REPLY",
			source.stb.eq(1),
			source.reply.eq(1),
			source.ip_address.eq(sink.ip_address),
			If(source.ack,
				NextState("IDLE")
			)
		)
		fsm.act("UPDATE_TABLE",
			# XXX update memory
			NextState("IDLE")
		)
		found = Signal()
		fsm.act("CHECK_TABLE",
			# XXX add a kind of CAM?
			If(found,
				NextState("PRESENT_RESPONSE")
			).Else(
				NextState("SEND_REQUEST")
			)
		)
		fsm.act("SEND_REQUEST",
			source.stb.eq(1),
			source.request.eq(1),
			source.ip_address.eq(request.ip_address),
			If(source.ack,
				NextState("IDLE")
			)
		)
		fsm.act("PRESENT_RESPONSE",
			response.stb.eq(1),
			response.failed.eq(0), # XXX add timeout to trigger failed
			response.mac_address.eq(0x12345678abcd), # XXX get mac address from table
			If(response.ack,
				NextState("IDLE")
			)
		)

class LiteEthARP(Module):
	def __init__(self, mac_address, ip_address):
		self.submodules.tx = LiteEthARPTX(mac_address, ip_address)
		self.submodules.rx = LiteEthARPRX(mac_address, ip_address)
		self.submodules.table = LiteEthARPTable()
		self.comb += [
			Record.connect(self.rx.source, self.table.sink),
			Record.connect(self.table.source, self.tx.sink)
		]
		self.sink, self.source = self.rx.sink, self.tx.source
		self.request, self.response = self.table.request, self.table.response
