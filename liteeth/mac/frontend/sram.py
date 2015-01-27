from migen.fhdl.std import *
from migen.genlib.fifo import SyncFIFO
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import chooser
from migen.flow.actor import Sink, Source
from migen.bank.description import *
from migen.bank.eventmanager import *

from liteethernet.common import *
from liteethernet.mac.common import *

class SRAMWriter(Module, AutoCSR):
	def __init__(self, depth, nslots=2):
		self.sink = sink = Sink(eth_description(32))
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
				If(fifo.writable,
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
			fifo.we.eq(1),
			fifo.din.slot.eq(slot),
			fifo.din.length.eq(cnt),
			NextState("IDLE")
		)

		self.comb += [
			fifo.re.eq(self.ev.available.clear),
			self.ev.available.trigger.eq(fifo.readable),
			self._slot.status.eq(fifo.dout.slot),
			self._length.status.eq(fifo.dout.length),
		]

		# memory
		mems = [None]*nslots
		ports = [None]*nslots
		for n in range(nslots):
			mems[n] = Memory(32, depth)
			ports[n] = mems[n].get_port(write_capable=True)
			self.specials += ports[n]
		self.mems = mems

		cases = {}
		for n, port in enumerate(ports):
			cases[n] = [
				ports[n].adr.eq(cnt[2:]),
				ports[n].dat_w.eq(sink.d),
				If(sink.stb & ongoing,
					ports[n].we.eq(0xf)
				)
			]
		self.comb += Case(slot, cases)


class SRAMReader(Module, AutoCSR):
	def __init__(self, depth, nslots=2):
		self.source = source = Source(eth_description(32))

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
			fifo.we.eq(self._start.re),
			fifo.din.slot.eq(self._slot.storage),
			fifo.din.length.eq(self._length.storage),
			self._ready.status.eq(fifo.writable)
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
			If(fifo.readable,
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
		length_lsb = fifo.dout.length[0:2]
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
			fifo.re.eq(1),
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
		self.comb += last.eq(cnt + 4 >= fifo.dout.length)
		self.sync += last_d.eq(last)

		# memory
		rd_slot = fifo.dout.slot

		mems = [None]*nslots
		ports = [None]*nslots
		for n in range(nslots):
			mems[n] = Memory(32, depth)
			ports[n] = mems[n].get_port()
			self.specials += ports[n]
		self.mems = mems

		cases = {}
		for n, port in enumerate(ports):
			self.comb += ports[n].adr.eq(cnt[2:])
			cases[n] = [source.d.eq(port.dat_r)]
		self.comb += Case(rd_slot, cases)
