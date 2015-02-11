from liteeth.common import *
from migen.bus import wishbone

class LiteEthEtherboneWishboneMaster(Module):
	def __init__(self):
		self.wr_sink = wr_sink = Sink(eth_etherbone_mmap_description(32))
		self.rd_sink = rd_sink = Sink(eth_etherbone_mmap_description(32))
		self.wr_source = wr_source = Source(eth_etherbone_mmap_description(32))
		self.rd_source = rd_source = Source(eth_etherbone_mmap_description(32))
		self.bus = bus = wishbone.Interface()
		###s

		data = FlipFlop(32)
		self.submodules += data
		self.comb += data.d.eq(bus.dat_r)

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			wr_sink.ack.eq(1),
			rd_sink.ack.eq(1),
			If(wr_sink.stb & wr_sink.sop,
				wr_sink.ack.eq(0),
				NextState("WRITE_DATA")
			).Elif(rd_sink.stb & rd_sink.sop,
				rd_sink.ack.eq(0),
				NextState("READ_DATA")
			)
		)
		fsm.act("WRITE_DATA",
			bus.adr.eq(wr_sink.addr),
			bus.dat_w.eq(wr_sink.data),
			bus.sel.eq(wr_sink.be),
			bus.stb.eq(wr_sink.stb),
			bus.we.eq(1),
			bus.cyc.eq(1),
			If(bus.stb & bus.ack,
				wr_sink.ack.eq(1),
				If(wr_sink.eop,
					NextState("IDLE")
				)
			)
		)
		fsm.act("READ_DATA",
			bus.adr.eq(rd_sink.addr),
			bus.sel.eq(rd_sink.be),
			bus.stb.eq(rd_sink.stb),
			bus.cyc.eq(1),
			If(bus.stb & bus.ack,
				data.ce.eq(1),
				NextState("SEND_DATA")
			)
		)
		fsm.act("SEND_DATA",
			wr_source.stb.eq(rd_sink.stb),
			wr_source.sop.eq(rd_sink.sop),
			wr_source.eop.eq(rd_sink.eop),
			wr_source.base_addr.eq(rd_sink.base_addr),
			wr_source.addr.eq(rd_sink.addr),
			wr_source.count.eq(rd_sink.count),
			wr_source.be.eq(rd_sink.be),
			#wr_source.data.eq(data.q),
			wr_source.data.eq(0x12345678), # XXX
			If(wr_source.stb & wr_source.ack,
				rd_sink.ack.eq(1),
				If(wr_source.eop,
					NextState("IDLE")
				).Else(
					NextState("READ_DATA")
				)
			)
		)
