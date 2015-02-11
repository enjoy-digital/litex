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
		self.write_source = write_source = Source(eth_etherbone_mmap_description(32))
		self.read_source = read_source = Source(eth_etherbone_mmap_description(32))
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
					NextState("RECEIVE_READS")
				).Elif(sink.rcount,
					NextState("RECEIVE_READS")
				)
			)
		)
		fsm.act("RECEIVE_WRITES",
			write_source.stb.eq(sink.stb),
			write_source.sop.eq(counter.value == 0),
			write_source.eop.eq(counter.value == sink.wcount-1),
			write_source.count.eq(sink.wcount),
			write_source.base_addr.eq(base_addr.q),
			write_source.data_addr.eq(sink.data),
			sink.ack.eq(write_source.ack),
			If(write_source.stb & write_source.ack,
				counter.ce.eq(1),
				If(write_source.eop,
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
			read_source.stb.eq(sink.stb),
			read_source.sop.eq(counter.value == 0),
			read_source.eop.eq(counter.value == sink.rcount-1),
			read_source.count.eq(sink.rcount),
			read_source.base_addr.eq(base_addr.q),
			read_source.data_addr.eq(sink.data),
			sink.ack.eq(read_source.ack),
			If(read_source.stb & read_source.ack,
				counter.ce.eq(1),
				If(read_source.eop,
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

		self.submodules.base_addr = base_addr = FlipFlop(32)
		self.comb += base_addr.d.eq(wr_buffer.source.data_addr)

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			wr_buffer.source.ack.eq(1),
			If(wr_buffer.source.stb & wr_buffer.source.sop,
				wr_buffer.source.ack.eq(0),
				base_addr.ce.eq(1),
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
			source.data.eq(base_addr.q),
			If(source.ack,
				NextState("SEND_DATA")
			)
		)
		fsm.act("SEND_DATA",
			source.stb.eq(wr_buffer.source.stb),
			source.sop.eq(0),
			source.eop.eq(wr_buffer.source.eop),
			source.data.eq(wr_buffer.source.data_addr),
			If(source.stb & source.eop & source.ack,
				NextState("IDLE")
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
			Record.connect(depacketizer.source, receiver.sink)
		]

		self.submodules.sender = sender =  LiteEthEtherboneRecordSender()
		self.submodules.packetizer = packetizer = LiteEthEtherboneRecordPacketizer()
		self.comb += [
			Record.connect(sender.source, packetizer.sink),
			Record.connect(packetizer.source, source)
		]
