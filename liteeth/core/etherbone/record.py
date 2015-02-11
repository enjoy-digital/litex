from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

class LiteEthEtherboneRecordPacketizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_etherbone_record_description(32),
			eth_etherbone_packet_user_description(32),
			etherbone_record_header,
			etherbone_record_header_len)

class LiteEthEtherboneRecordDepacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_etherbone_packet_user_description(32),
			eth_etherbone_record_description(32),
			etherbone_record_header,
			etherbone_record_header_len)

class LiteEthEtherboneRecordReceiver(Module):
	def __init__(self):
		self.sink = sink = Sink(eth_etherbone_record_description(32))
		self.wr_source = wr_source = Source(eth_etherbone_mmap_description(32))
		self.rd_source = rd_source = Source(eth_etherbone_mmap_description(32))
		###

		self.submodules.base_addr = base_addr = FlipFlop(32)
		self.comb += base_addr.d.eq(sink.data)

		self.submodules.counter = counter = Counter(max=512)

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			sink.ack.eq(1),
			counter.reset.eq(1),
			If(sink.stb & sink.sop,
				base_addr.ce.eq(1),
				If(sink.wcount,
					NextState("RECEIVE_WRITES")
				).Elif(sink.rcount,
					NextState("RECEIVE_READS")
				)
			)
		)
		fsm.act("RECEIVE_WRITES",
			wr_source.stb.eq(sink.stb),
			wr_source.sop.eq(counter.value == 0),
			wr_source.eop.eq(counter.value == sink.wcount-1),
			wr_source.count.eq(sink.wcount),
			wr_source.be.eq(sink.byte_enable),
			wr_source.addr.eq(base_addr.q + counter.value),
			wr_source.data.eq(sink.data),
			sink.ack.eq(wr_source.ack),
			If(wr_source.stb & wr_source.ack,
				counter.ce.eq(1),
				If(wr_source.eop,
					If(sink.rcount,
						NextState("RECEIVE_BASE_RET_ADDR")
					).Else(
						NextState("IDLE")
					)
				)
			)
		)
		fsm.act("RECEIVE_BASE_RET_ADDR",
			counter.reset.eq(1),
			If(sink.stb & sink.sop,
				base_addr.ce.eq(1),
				NextState("RECEIVE_READS")
			)
		)
		fsm.act("RECEIVE_READS",
			rd_source.stb.eq(sink.stb),
			rd_source.sop.eq(counter.value == 0),
			rd_source.eop.eq(counter.value == sink.rcount-1),
			rd_source.count.eq(sink.rcount),
			rd_source.base_addr.eq(base_addr.q),
			rd_source.addr.eq(sink.data),
			sink.ack.eq(rd_source.ack),
			If(rd_source.stb & rd_source.ack,
				counter.ce.eq(1),
				If(rd_source.eop,
					NextState("IDLE")
				)
			)
		)

# Note: for now only support writes from the FPGA
class LiteEthEtherboneRecordSender(Module):
	def __init__(self):
		self.wr_sink = wr_sink = Sink(eth_etherbone_mmap_description(32))
		self.rd_sink = rd_sink = Sink(eth_etherbone_mmap_description(32))
		self.source = source = Source(eth_etherbone_record_description(32))
		###
		self.submodules.wr_buffer = wr_buffer = PacketBuffer(eth_etherbone_mmap_description(32), 512)
		self.comb += Record.connect(wr_sink, wr_buffer.sink)

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			wr_buffer.source.ack.eq(1),
			If(wr_buffer.source.stb & wr_buffer.source.sop,
				wr_buffer.source.ack.eq(0),
				NextState("SEND_BASE_ADDRESS")
			)
		)
		self.comb += [
			source.byte_enable.eq(wr_buffer.source.be),
			source.wcount.eq(wr_buffer.source.count),
			source.rcount.eq(0)
		]

		fsm.act("SEND_BASE_ADDRESS",
			source.stb.eq(wr_buffer.source.stb),
			source.sop.eq(1),
			source.eop.eq(0),
			source.data.eq(wr_buffer.source.base_addr),
			If(source.ack,
				NextState("SEND_DATA")
			)
		)
		fsm.act("SEND_DATA",
			source.stb.eq(wr_buffer.source.stb),
			source.sop.eq(0),
			source.eop.eq(wr_buffer.source.eop),
			source.data.eq(wr_buffer.source.data),
			If(source.stb & source.ack,
				wr_buffer.source.ack.eq(1),
				If(source.eop,
					NextState("IDLE")
				)
			)
		)

# Note: for now only support 1 record per packet
class LiteEthEtherboneRecord(Module):
	def __init__(self):
		self.sink = sink = Sink(eth_etherbone_packet_user_description(32))
		self.source = source = Sink(eth_etherbone_packet_user_description(32))
		###
		self.submodules.depacketizer = depacketizer = LiteEthEtherboneRecordDepacketizer()
		self.submodules.receiver = receiver =  LiteEthEtherboneRecordReceiver()
		self.comb += [
			Record.connect(sink, depacketizer.sink),
			Record.connect(depacketizer.source, receiver.sink),
			receiver.sink.data.eq(reverse_bytes(depacketizer.source.data)) # clarify this
		]

		last_ip_address = Signal(32) # XXX for test
		last_src_port = Signal(16)   # XXX for test
		last_dst_port = Signal(16)   # XXX for test

		self.sync += [
			If(sink.stb & sink.sop & sink.ack,
				last_ip_address.eq(sink.ip_address),
				last_src_port.eq(sink.src_port),
				last_dst_port.eq(sink.dst_port)
			)
		]

		self.submodules.sender = sender =  LiteEthEtherboneRecordSender()
		self.submodules.packetizer = packetizer = LiteEthEtherboneRecordPacketizer()
		self.comb += [
			Record.connect(sender.source, packetizer.sink),
			packetizer.sink.data.eq(reverse_bytes(sender.source.data)), # clarify this
			Record.connect(packetizer.source, source),
			source.length.eq(sender.source.wcount*4 + 4),
			source.ip_address.eq(last_ip_address),
			source.src_port.eq(last_src_port),
			source.dst_port.eq(last_dst_port)
		]
