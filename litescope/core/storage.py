from litescope.common import *

class LiteScopeRunLengthEncoderUnit(Module):
	def __init__(self, dw, length=1024):
		self.dw = dw
		self.length = length

		self.sink = sink = Sink(data_layout(dw))
		self.source = source = Source(data_layout(dw))

		self.enable = Signal()
		###
		sink_d = Sink(data_layout(dw))
		self.sync += If(sink.stb, sink_d.eq(sink))

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
		self.comb += change.eq(sink.stb & (sink.dat != sink_d.dat))

		fsm = FSM(reset_state="BYPASS")
		self.submodules += fsm
		fsm.act("BYPASS",
			Record.connect(sink_d, source),
			cnt_reset.eq(1),
			If(self.enable & ~change & sink.stb, NextState("COUNT"))
		)
		fsm.act("COUNT",
			cnt_inc.eq(sink.stb),
			If(change | cnt_max | ~self.enable,
				source.stb.eq(1),
				source.dat[dw-1].eq(1), # Set RLE bit
				source.dat[:flen(cnt)].eq(cnt),
				NextState("BYPASS")
			)
		)

class LiteScopeRunLengthEncoder(LiteScopeRunLengthEncoderUnit, AutoCSR):
	def __init__(self, dw, length=1024):
		LiteScopeRunLengthEncoderUnit.__init__(self, dw, length)
		self._enable = CSRStorage()
		###
		self.comb += self.enable.eq(self_enable.storage)

class LiteScopeRecorder(Module, AutoCSR):
	def __init__(self, dw, depth):
		self.dw = dw

		self.trigger_sink = trigger_sink = Sink(hit_layout())
		self.data_sink = data_sink = Sink(data_layout(dw))

		self._trigger = CSR()
		self._length = CSRStorage(bits_for(depth))
		self._offset = CSRStorage(bits_for(depth))
		self._done = CSRStatus()

		self._source_stb = CSRStatus()
		self._source_ack = CSR()
		self._source_data = CSRStatus(dw)

		###

		fifo = InsertReset(SyncFIFO(data_layout(dw), depth, buffered=True))
		self.submodules += fifo

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		self.comb += [
			self._source_stb.status.eq(fifo.source.stb),
			self._source_data.status.eq(fifo.source.data)
		]
		fsm.act("IDLE",
			self._done.status.eq(1),
			If(self._trigger.re,
				NextState("PRE_HIT_RECORDING"),
				fifo.reset.eq(1),
			),
			fifo.source.ack.eq(self._source_ack.re)
		)
		fsm.act("PRE_HIT_RECORDING",
			fifo.sink.stb.eq(data_sink.stb),
			fifo.sink.data.eq(data_sink.data),
			data_sink.ack.eq(fifo.sink.ack),

			fifo.source.ack.eq(fifo.fifo.level >= self._offset.storage),
			If(trigger_sink.stb & trigger_sink.hit, NextState("POST_HIT_RECORDING"))
		)
		fsm.act("POST_HIT_RECORDING",
			fifo.sink.stb.eq(data_sink.stb),
			fifo.sink.data.eq(data_sink.data),
			data_sink.ack.eq(fifo.sink.ack),

			If(~fifo.sink.ack | (fifo.fifo.level >= self._length.storage), NextState("IDLE"))
		)
