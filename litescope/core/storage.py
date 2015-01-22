from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.fifo import SyncFIFOBuffered as SyncFIFO
from migen.genlib.fsm import FSM, NextState
from migen.genlib.record import *

from litescope.common import *

class LiteScopeRunLengthEncoder(Module, AutoCSR):
	def __init__(self, width, length=1024):
		self.width = width
		self.length = length

		self.sink = Record(dat_layout(width))
		self.source = Record(dat_layout(width))

		self._enable = CSRStorage()

		###

		enable = self._enable.storage

		sink_d = Record(dat_layout(width))
		self.sync += If(self.sink.stb, sink_d.eq(self.sink))

		cnt = Signal(max=length)
		cnt_inc = Signal()
		cnt_reset = Signal()
		cnt_max = Signal()

		self.sync += \
			If(cnt_reset,
				cnt.eq(1),
			).Elif(cnt_inc,
				cnt.eq(cnt+1)
			)
		self.comb += cnt_max.eq(cnt == length)

		change = Signal()
		self.comb += change.eq(self.sink.stb & (self.sink.dat != sink_d.dat))

		fsm = FSM(reset_state="BYPASS")
		self.submodules += fsm

		fsm.act("BYPASS",
			sink_d.connect(self.source),
			cnt_reset.eq(1),
			If(enable & ~change & self.sink.stb, NextState("COUNT"))
		)

		fsm.act("COUNT",
			cnt_inc.eq(self.sink.stb),
			If(change | cnt_max | ~enable,
				self.source.stb.eq(1),
				self.source.dat[width-1].eq(1), # Set RLE bit
				self.source.dat[:flen(cnt)].eq(cnt),
				NextState("BYPASS")
			)
		),

class LiteScopeRecorder(Module, AutoCSR):
	def __init__(self, width, depth):
		self.width = width

		self.trig_sink = Record(hit_layout())
		self.dat_sink = Record(dat_layout(width))

		self._trigger = CSR()
		self._length = CSRStorage(bits_for(depth))
		self._offset = CSRStorage(bits_for(depth))
		self._done = CSRStatus()

		self._read_en = CSR()
		self._read_empty = CSRStatus()
		self._read_dat = CSRStatus(width)

		###

		fifo = InsertReset(SyncFIFO(width, depth))
		self.submodules += fifo

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm


		self.comb += [
			self._read_empty.status.eq(~fifo.readable),
			self._read_dat.status.eq(fifo.dout),
		]

		fsm.act("IDLE",
			If(self._trigger.re & self._trigger.r,
				NextState("PRE_HIT_RECORDING"),
				fifo.reset.eq(1),
			),
			fifo.re.eq(self._read_en.re & self._read_en.r),
			self._done.status.eq(1)
		)

		fsm.act("PRE_HIT_RECORDING",
			fifo.we.eq(self.dat_sink.stb),
			fifo.din.eq(self.dat_sink.dat),

			fifo.re.eq(fifo.level >= self._offset.storage),

			If(self.trig_sink.stb & self.trig_sink.hit, NextState("POST_HIT_RECORDING"))
		)

		fsm.act("POST_HIT_RECORDING",
			fifo.we.eq(self.dat_sink.stb),
			fifo.din.eq(self.dat_sink.dat),

			If(~fifo.writable | (fifo.level >= self._length.storage), NextState("IDLE"))
		)
