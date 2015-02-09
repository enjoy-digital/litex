from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

class LiteEthEtherboneDepacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_udp_user_description(8),
			eth_etherbone_description(8),
			etherbone_header,
			etherbone_header_len)

class LiteEthEtherbonePacketizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_etherbone_description(8),
			eth_udp_user_description(8),
			etherbone_header,
			etherbone_header_len)

class LiteEthEtherboneTX(Module):
	def __init__(self, udp_port):
		self.sink = sink = Sink(eth_etherbone_user_description(8))
		self.source = source = Source(eth_udp_user_description(8))
		###
		self.submodules.packetizer = packetizer = LiteEthUDPPacketizer()
		self.comb += [
			packetizer.sink.stb.eq(sink.stb),
			packetizer.sink.sop.eq(sink.sop),
			packetizer.sink.eop.eq(sink.eop),
			sink.ack.eq(packetizer.sink.ack),

			packetizer.sink.magic.eq(etherbone_magic),
			packetizer.sink.portsize.eq(32), # XXX
			packetizer.sink.addrsize.eq(32), # XXX
			packetizer.sink.pf.eq(0), # XXX
			packetizer.sink.version.eq(etherbone_version),

			packetizer.sink.wff.eq(0), # XXX
			packetizer.sink.wca.eq(0), # XXX
			packetizer.sink.cyc.eq(0), # XXX
			packetizer.sink.rff.eq(0), # XXX
			packetizer.sink.rca.eq(0), # XXX
			packetizer.sink.bca.eq(0), # XXX

			packetizer.sink.rcount.eq(sink.rcount),
			packetier.sink.wconut.eq(sink.wcount),

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
		self.comb += [
			source.src_port.eq(0x1234), # XXX,
			source.dst_port.eq(udp_port),
			source.ip_address.eq(sink.ip_address),
			source.length.eq(sink.length + eth_etherbone_header_len)
		]
		fsm.act("SEND",
			Record.connect(packetizer.source, source),
			If(source.stb & source.eop & source.ack,
				NextState("IDLE")
			)
		)

class LiteEthEtherboneRX(Module):
	def __init__(self):
		self.sink = sink = Sink(eth_udp_user_description(8))
		self.source = source = Source(eth_etherbone_user_description(8))
		###
		self.submodules.depacketizer = depacketizer = LiteEtherboneDepacketizer()
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
			(depacketizer.source.magic == etherbone_magic) &
			(depacketizer.source.version == etherbone_version)
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
			source.rcount.eq(depacketizer.source.rcount),
			source.wcount.eq(depacketizer.source.wcount),
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

class LiteEthEtherboneWishboneMaster(Module):
	def __init__(self):
		self.sink = sink = Sink(eth_etherbone_user_description(8))
		self.source = source = Source(eth_etherbone_description(8))
		self.bus = bus = wishbone.Interface()
		###

		self.submodules.base_addr = base_addr = FlipFlop(32)
		self.comb += self.base_addr.d.eq(self.sink.data)
		self.submodules.counter = counter = Counter(32)

		self.submodules.fifo = fifo = SyncFIFO([("data", 32)], 256)

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			sink.ack.eq(1),
			counter.reset.eq(1),
			If(sink.stb & sink.sop,
				If(sink.wcount > 0,
					self.base_addr.ce.eq(1),
					NextState("WRITE_DATA")
				).Elif(sink.rcount > 0,
					self.base_addr.ce.eq(1),
					NextState("READ_DATA")
				)
			)
		)
		fsm.act("WRITE_DATA",
			bus.adr.eq(base_addr + self.counter.value),
			bus.dat_w.eq(sink.data),
			bus.sel.eq(0xf), # XXX?
			bus.stb.eq(sink.stb),
			bus.we.eq(1),
			bus.cyc.eq(1),
			If(bus.stb & bus.ack,
				sink.ack.eq(1),
				counter.ce.eq(1),
				If(counter.value == sink.wcount-1,
					If(sink.rcount > 0,
						counter.reset.eq(1)
						NextState("READ_DATA")
					).Else(
						NextState("TERMINATE")
					)
				)
			)
		)
		fsm.act("CHECK_READ",
			If(sink.rcount > 0,
				If(sink.stb,
					sink.ack.eq(1),
					base_addr.ce.eq(1),
					NextState("READ_DATA")
				)
			).Else(
					NextState("IDLE")
			)
		)
		fsm.act("READ_DATA",
			bus.adr.eq(self.sink.data),
			bus.sel.eq(0xf),
			bus.stb.eq(1),
			bus.we.eq(0),
			bus.cyc.eq(1),
			If(bus.stb & bus.ack,
				sink.ack.eq(1),
				counter.ce.eq(1),
				fifo.sink.stb.eq(1),
				fifo.sink.sop.eq(counter == 0),
				fifo.sink.data.eq(bus.dat_r),
				If(counter.value == sink.rcount-1,
					fifo.sink.eop.eq(1),
					NextState("PRESENT_DATA")
				)
			)
		)
		fsm.act("PRESENT_DATA",
			source.stb.eq(fifo.stb),
			source.sop.eq(fifo.sop),
			source.eop.eq(fifo.eop),
			fifo.ack.eq(source.ack),
			source.length.eq(sink.rcount+1),
			source.wcount.eq(sink.rcount),
			source.rcount.eq(0),
			If(source.stb & source.eop & source.ack,
				NextState("IDLE")
			)
		)

class LiteEthEtherbone(Module):
	def __init__(self, udp, udp_port):
		self.submodules.tx = tx = LiteEthEtherboneTX(udp_port)
		self.submodules.rx = rx = LiteEthEtherboneRX()
		udp_port = udp.crossbar.get_port(udp_port)
		self.comb += [
			Record.connect(tx.source, udp_port.sink),
			Record.connect(udp_port.source, rx.sink)
		]
		self.master = master = LiteEthEtherboneWishboneMaster()
		self.comb += [
			Record.connect(rx.source.connect(master.sink)),
			Record.connect(master.source.connect(tx.sink))
		]
