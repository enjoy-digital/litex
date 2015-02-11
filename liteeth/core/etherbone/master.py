from liteeth.common import *

class LiteEthEtherboneWishboneMaster(Module):
	def __init__(self):
		self.sink = sink = Sink(eth_etherbone_user_description(32))
		self.source = source = Source(eth_etherbone_description(32))
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
