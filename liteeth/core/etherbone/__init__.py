from liteeth.common import *
from liteeth.core.etherbone import common

class LiteEthEtherboneTX(Module):
	def __init__(self, udp_port):
		self.sink = sink = Sink(eth_etherbone_user_description(32))
		self.source = source = Source(eth_udp_user_description(32))
		###
		self.submodules.packetizer = packetizer = LiteEthEtherbonePacketizer()
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
		self.sink = sink = Sink(eth_udp_user_description(32))
		self.source = source = Source(eth_etherbone_user_description(32))
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

class LiteEthEtherbone(Module):
	def __init__(self, udp, udp_port):
		self.submodules.tx = tx = LiteEthEtherboneTX(udp_port)
		self.submodules.rx = rx = LiteEthEtherboneRX()
		udp_port = udp.crossbar.get_port(udp_port, dw=32)
		self.comb += [
			Record.connect(tx.source, udp_port.sink),
			Record.connect(udp_port.source, rx.sink)
		]
		self.master = master = LiteEthEtherboneWishboneMaster()
		self.comb += [
			Record.connect(rx.source.connect(master.sink)),
			Record.connect(master.source.connect(tx.sink))
		]
