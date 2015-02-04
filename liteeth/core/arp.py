from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

_arp_table_layout = [
		("reply", 1),
		("request", 1),
		("ip_address", 32),
		("mac_address", 48)
	]

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

class LiteEthARPTX(Module):
	def __init__(self, mac_address, ip_address):
		self.sink = sink = Sink(_arp_table_layout)
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
			source.hwtype.eq(arp_hwtype_ethernet),
			source.proto.eq(arp_proto_ip),
			source.hwsize.eq(6),
			source.protosize.eq(4),
			source.sender_mac.eq(mac_address),
			source.sender_ip.eq(ip_address),
			If(sink.reply,
				source.opcode.eq(arp_opcode_reply),
				source.target_mac.eq(sink.mac_address),
				source.target_ip.eq(sink.ip_address)
			).Elif(sink.request,
				source.opcode.eq(arp_opcode_request),
				source.target_mac.eq(0xffffffffffff),
				source.target_ip.eq(sink.ip_address)
			)
		]
		fsm.act("SEND",
			source.stb.eq(1),
			source.sop.eq(counter.value == 0),
			source.eop.eq(counter.value == arp_packet_length-1),
			Record.connect(packetizer.source, self.source),
			self.source.target_mac.eq(source.target_mac),
			self.source.sender_mac.eq(mac_address),
			self.source.ethernet_type.eq(ethernet_type_arp),
			If(self.source.stb & self.source.ack,
				sink.ack.eq(source.eop),
				counter.ce.eq(1),
				If(self.source.eop,
					NextState("IDLE")
				)
			)
		)

class LiteEthARPRX(Module):
	def __init__(self, mac_address, ip_address):
		self.sink = Sink(eth_mac_description(8))
		self.source = source = Source(_arp_table_layout)
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
				sink.ack.eq(0),
				NextState("CHECK")
			)
		)
		valid = Signal()
		self.comb += valid.eq(
			sink.stb &
			(sink.hwtype == arp_hwtype_ethernet) &
			(sink.proto == arp_proto_ip) &
			(sink.hwsize == 6) &
			(sink.protosize == 4) &
			(sink.target_ip == ip_address)
		)
		reply = Signal()
		request = Signal()
		self.comb += Case(sink.opcode, {
			arp_opcode_request	:	[request.eq(1)],
			arp_opcode_reply	:	[reply.eq(1)],
			"default"			:	[]
			})
		self.comb += [
			source.ip_address.eq(sink.sender_ip),
			source.mac_address.eq(sink.sender_mac)
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

class LiteEthARPTable(Module):
	def __init__(self):
		self.sink = sink = Sink(_arp_table_layout) 		# from arp_rx
		self.source = source = Source(_arp_table_layout) 	# to arp_tx

		# Request/Response interface
		self.request = request = Sink(arp_table_request_layout)
		self.response = response = Source(arp_table_response_layout)
		###
		request_timeout = Timeout(512)	# XXX fix me 100ms?
		request_pending = FlipFlop()
		request_ip_address = FlipFlop(32, reset=0xffffffff) # XXX add cached_valid?
		self.submodules += request_timeout, request_pending, request_ip_address
		self.comb += [
			request_timeout.ce.eq(request_pending.q),
			request_pending.d.eq(1),
			request_ip_address.d.eq(request.ip_address)
		]

		# Note: Store only one ip/mac couple, replace this with
		# a real ARP table
		update = Signal()
		cached_ip_address = Signal(32)
		cached_mac_address = Signal(48)

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			# Note: for simplicicy, if APR table is busy response from arp_rx
			# is lost. This is compensated by the protocol (retrys)
			If(sink.stb & sink.request,
				NextState("SEND_REPLY")
			).Elif(sink.stb & sink.reply & request_pending.q,
				NextState("UPDATE_TABLE"),
			).Elif(request.stb | (request_pending.q & request_timeout.reached),
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
			request_pending.reset.eq(1),
			update.eq(1),
			NextState("CHECK_TABLE")
		)
		self.sync += [
			If(update,
				cached_ip_address.eq(sink.ip_address),
				cached_mac_address.eq(sink.mac_address)
			)
		]
		found = Signal()
		fsm.act("CHECK_TABLE",
			# XXX: add a live time for cached_mac_address
			If(request_ip_address.q == cached_ip_address,
				request_ip_address.reset.eq(1),
				NextState("PRESENT_RESPONSE"),
			).Elif(request.ip_address == cached_ip_address,
				request.ack.eq(request.stb),
				NextState("PRESENT_RESPONSE"),
			).Else(
				request_ip_address.ce.eq(1),
				NextState("SEND_REQUEST")
			)
		)
		fsm.act("SEND_REQUEST",
			source.stb.eq(1),
			source.request.eq(1),
			source.ip_address.eq(request.ip_address),
			If(source.ack,
				request_timeout.reset.eq(1),
				request_pending.ce.eq(1),
				request.ack.eq(1),
				NextState("IDLE")
			)
		)
		fsm.act("PRESENT_RESPONSE",
			response.stb.eq(1),
			response.failed.eq(0), # XXX add timeout to trigger failed
			response.mac_address.eq(cached_mac_address),
			If(response.ack,
				NextState("IDLE")
			)
		)

class LiteEthARP(Module):
	def __init__(self, mac, mac_address, ip_address):
		self.submodules.tx = LiteEthARPTX(mac_address, ip_address)
		self.submodules.rx = LiteEthARPRX(mac_address, ip_address)
		self.submodules.table = LiteEthARPTable()
		self.comb += [
			Record.connect(self.rx.source, self.table.sink),
			Record.connect(self.table.source, self.tx.sink)
		]
		mac_port = mac.crossbar.get_port(ethernet_type_arp)
		self.comb += [
			Record.connect(self.tx.source, mac_port.sink),
			Record.connect(mac_port.source, self.rx.sink)
		]
