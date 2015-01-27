from litescope.common import *

class LiteScopeSubSamplerUnit(Module):
	def __init__(self, dw):
		self.sink = sink = Sink(data_layout(dw))
		self.source = source = Source(data_layout(dw))
		self.value = Signal(32)
		###
		self.submodules.counter = Counter(bits_sign=32)
		done = Signal()
		self.comb += [
			done.eq(self.counter.value >= self.value),
			Record.connect(sink, source),
			source.stb.eq(sink.stb & done),
			self.counter.ce.eq(source.ack),
			self.counter.reset.eq(source.stb & source.ack & done)
		]

class LiteScopeSubSampler(LiteScopeSubSamplerUnit, AutoCSR):
	def __init__(self, dw):
		LiteScopeSubSamplerUnit.__init__(self, dw)
		self._value = CSRStorage(32)
		###
		self.comb += self.value.eq(self._value.storage)

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

class LiteScopeRecorderUnit(Module):
	def __init__(self, dw, depth):
		self.dw = dw
		self.depth = depth

		self.trigger_sink = trigger_sink = Sink(hit_layout())
		self.data_sink = data_sink = Sink(data_layout(dw))

		self.trigger = Signal()
		self.qualifier = Signal()
		self.length = Signal(bits_for(depth))
		self.offset = Signal(bits_for(depth))
		self.done = Signal()

		self.source = Source(data_layout(dw))

		###

		fifo = InsertReset(SyncFIFO(data_layout(dw), depth, buffered=True))
		self.submodules += fifo

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		self.comb += [
			self.source.stb.eq(fifo.source.stb),
			self.source.data.eq(fifo.source.data)
		]
		fsm.act("IDLE",
			self.done.eq(1),
			If(self.trigger,
				NextState("PRE_HIT_RECORDING"),
				fifo.reset.eq(1),
			),
			fifo.source.ack.eq(self.source.ack)
		)
		fsm.act("PRE_HIT_RECORDING",
			fifo.sink.stb.eq(data_sink.stb),
			fifo.sink.data.eq(data_sink.data),
			data_sink.ack.eq(fifo.sink.ack),

			fifo.source.ack.eq(fifo.fifo.level >= self.offset),
			If(trigger_sink.stb & trigger_sink.hit, NextState("POST_HIT_RECORDING"))
		)
		fsm.act("POST_HIT_RECORDING",
			If(self.qualifier,
				fifo.sink.stb.eq(trigger_sink.stb & trigger_sink.hit & data_sink.stb)
			).Else(
				fifo.sink.stb.eq(data_sink.stb)
			),
			fifo.sink.data.eq(data_sink.data),
			data_sink.ack.eq(fifo.sink.ack),

			If(~fifo.sink.ack | (fifo.fifo.level >= self.length), NextState("IDLE"))
		)

class LiteScopeRecorder(LiteScopeRecorderUnit, AutoCSR):
	def __init__(self, dw, depth):
		LiteScopeRecorderUnit.__init__(self, dw, depth)

		self._trigger = CSR()
		self._qualifier = CSRStorage()
		self._length = CSRStorage(bits_for(depth))
		self._offset = CSRStorage(bits_for(depth))
		self._done = CSRStatus()

		self._source_stb = CSRStatus()
		self._source_ack = CSR()
		self._source_data = CSRStatus(dw)

		###

		self.comb += [
			self.trigger.eq(self._trigger.re),
			self.qualifier.eq(self._qualifier.storage),
			self.length.eq(self._length.storage),
			self.offset.eq(self._offset.storage),
			self._done.status.eq(self.done),

			self._source_stb.status.eq(self.source.stb),
			self._source_data.status.eq(self.source.data),
			self.source.ack.eq(self._source_ack.re)
		]
