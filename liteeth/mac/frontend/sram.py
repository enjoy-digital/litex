from liteeth.common import *
from liteeth.mac.common import *

from migen.bank.description import *
from migen.bank.eventmanager import *

class LiteEthMACSRAMWriter(Module, AutoCSR):
	def __init__(self, dw, depth, nslots=2):
		self.sink = sink = Sink(eth_phy_description(dw))
		self.crc_error = Signal()

		slotbits = max(log2_int(nslots), 1)
		lengthbits = log2_int(depth*4) # length in bytes

		self._slot = CSRStatus(slotbits)
		self._length = CSRStatus(lengthbits)

		self.submodules.ev = EventManager()
		self.ev.available = EventSourceLevel()
		self.ev.finalize()

		###

		# packet dropped if no slot available
		sink.ack.reset = 1

		# length computation
		cnt = Signal(lengthbits)
		clr_cnt = Signal()
		inc_cnt = Signal()
		inc_val = Signal(3)
		self.comb += \
			If(sink.last_be[3],
				inc_val.eq(1)
			).Elif(sink.last_be[2],
				inc_val.eq(2)
			).Elif(sink.last_be[1],
				inc_val.eq(3)
			).Else(
				inc_val.eq(4)
			)
		self.sync += \
			If(clr_cnt,
				cnt.eq(0)
			).Elif(inc_cnt,
				cnt.eq(cnt+inc_val)
			)

		# slot computation
		slot = Signal(slotbits)
		inc_slot = Signal()
		self.sync += \
			If(inc_slot,
				If(slot == nslots-1,
					slot.eq(0),
				).Else(
					slot.eq(slot+1)
				)
			)
		ongoing = Signal()
		discard = Signal()

		# status fifo
		fifo = SyncFIFO([("slot", slotbits), ("length", lengthbits)], nslots)
		self.submodules += fifo

		# fsm
		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			inc_cnt.eq(sink.stb),
			If(sink.stb & sink.sop,
				ongoing.eq(1),
				If(fifo.sink.ack,
					NextState("WRITE")
				)
			)
		)
		fsm.act("WRITE",
			inc_cnt.eq(sink.stb),
			ongoing.eq(1),
			If(sink.stb & sink.eop,
				If((sink.error & sink.last_be) != 0,
					NextState("DISCARD")
				).Else(
					NextState("TERMINATE")
				)
			)
		)
		fsm.act("DISCARD",
			clr_cnt.eq(1),
			NextState("IDLE")
		)
		fsm.act("TERMINATE",
			clr_cnt.eq(1),
			inc_slot.eq(1),
			fifo.sink.stb.eq(1),
			fifo.sink.slot.eq(slot),
			fifo.sink.length.eq(cnt),
			NextState("IDLE")
		)

		self.comb += [
			fifo.source.ack.eq(self.ev.available.clear),
			self.ev.available.trigger.eq(fifo.source.stb),
			self._slot.status.eq(fifo.source.slot),
			self._length.status.eq(fifo.source.length),
		]

		# memory
		mems = [None]*nslots
		ports = [None]*nslots
		for n in range(nslots):
			mems[n] = Memory(dw, depth)
			ports[n] = mems[n].get_port(write_capable=True)
			self.specials += ports[n]
		self.mems = mems

		cases = {}
		for n, port in enumerate(ports):
			cases[n] = [
				ports[n].adr.eq(cnt[2:]),
				ports[n].dat_w.eq(sink.data),
				If(sink.stb & ongoing,
					ports[n].we.eq(0xf)
				)
			]
		self.comb += Case(slot, cases)


class LiteEthMACSRAMReader(Module, AutoCSR):
	def __init__(self, dw, depth, nslots=2):
		self.source = source = Source(eth_phy_description(dw))

		slotbits = max(log2_int(nslots), 1)
		lengthbits = log2_int(depth*4) # length in bytes
		self.lengthbits = lengthbits

		self._start = CSR()
		self._ready = CSRStatus()
		self._slot = CSRStorage(slotbits)
		self._length = CSRStorage(lengthbits)

		self.submodules.ev = EventManager()
		self.ev.done = EventSourcePulse()
		self.ev.finalize()

		###

		# command fifo
		fifo = SyncFIFO([("slot", slotbits), ("length", lengthbits)], nslots)
		self.submodules += fifo
		self.comb += [
			fifo.sink.stb.eq(self._start.re),
			fifo.sink.slot.eq(self._slot.storage),
			fifo.sink.length.eq(self._length.storage),
			self._ready.status.eq(fifo.sink.ack)
		]

		# length computation
		cnt = Signal(lengthbits)
		clr_cnt = Signal()
		inc_cnt = Signal()

		self.sync += \
			If(clr_cnt,
				cnt.eq(0)
			).Elif(inc_cnt,
				cnt.eq(cnt+4)
			)

		# fsm
		first = Signal()
		last  = Signal()
		last_d = Signal()

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			clr_cnt.eq(1),
			If(fifo.source.stb,
				NextState("CHECK")
			)
		)
		fsm.act("CHECK",
			If(~last_d,
				NextState("SEND"),
			).Else(
				NextState("END"),
			)
		)
		length_lsb = fifo.source.length[0:2]
		fsm.act("SEND",
			source.stb.eq(1),
			source.sop.eq(first),
			source.eop.eq(last),
			If(last,
				If(length_lsb == 3,
					source.last_be.eq(0b0010)
				).Elif(length_lsb == 2,
					source.last_be.eq(0b0100)
				).Elif(length_lsb == 1,
					source.last_be.eq(0b1000)
				).Else(
					source.last_be.eq(0b0001)
				)
			),
			If(source.ack,
				inc_cnt.eq(~last),
				NextState("CHECK")
			)
		)
		fsm.act("END",
			fifo.source.ack.eq(1),
			self.ev.done.trigger.eq(1),
			NextState("IDLE")
		)

		# first/last computation
		self.sync += [
			If(fsm.ongoing("IDLE"),
				first.eq(1)
			).Elif(source.stb & source.ack,
				first.eq(0)
			)
		]
		self.comb += last.eq(cnt + 4 >= fifo.source.length)
		self.sync += last_d.eq(last)

		# memory
		rd_slot = fifo.source.slot

		mems = [None]*nslots
		ports = [None]*nslots
		for n in range(nslots):
			mems[n] = Memory(dw, depth)
			ports[n] = mems[n].get_port()
			self.specials += ports[n]
		self.mems = mems

		cases = {}
		for n, port in enumerate(ports):
			self.comb += ports[n].adr.eq(cnt[2:])
			cases[n] = [source.data.eq(port.dat_r)]
		self.comb += Case(rd_slot, cases)

class LiteEthMACSRAM(Module, AutoCSR):
	def __init__(self, dw, depth, nrxslots, ntxslots):
		self.submodules.writer = LiteEthMACSRAMWriter(dw, depth, nrxslots)
		self.submodules.reader = LiteEthMACSRAMReader(dw, depth, ntxslots)
		self.submodules.ev = SharedIRQ(self.writer.ev, self.reader.ev)
		self.sink, self.source = self.writer.sink, self.reader.source
