from misoclib.liteeth.common import *
from misoclib.liteeth.generic import *

def _decode_header(h_dict, h_signal, obj):
	r = []
	for k, v in sorted(h_dict.items()):
		start = v.byte*8+v.offset
		end = start+v.width
		r.append(getattr(obj, k).eq(reverse_bytes(h_signal[start:end])))
	return r

class LiteEthDepacketizer(Module):
	def __init__(self, sink_description, source_description, header_type, header_length):
		self.sink = sink = Sink(sink_description)
		self.source = source = Source(source_description)
		self.header = Signal(header_length*8)
		###
		dw = flen(sink.data)

		header_words = (header_length*8)//dw

		shift = Signal()
		counter = Counter(max=max(header_words, 2))
		self.submodules += counter

		if header_words == 1:
			self.sync += \
				If(shift,
					self.header.eq(sink.data)
				)
		else:
			self.sync += \
				If(shift,
					self.header.eq(Cat(self.header[dw:], sink.data))
				)

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		if header_words == 1:
			idle_next_state = "COPY"
		else:
			idle_next_state = "RECEIVE_HEADER"

		fsm.act("IDLE",
			sink.ack.eq(1),
			counter.reset.eq(1),
			If(sink.stb,
				shift.eq(1),
				NextState(idle_next_state)
			)
		)
		if header_words != 1:
			fsm.act("RECEIVE_HEADER",
				sink.ack.eq(1),
				If(sink.stb,
					counter.ce.eq(1),
					shift.eq(1),
					If(counter.value == header_words-2,
						NextState("COPY")
					)
				)
			)
		no_payload = Signal()
		self.sync += \
			If(fsm.before_entering("COPY"),
				source.sop.eq(1),
				no_payload.eq(sink.eop)
			).Elif(source.stb & source.ack,
				source.sop.eq(0)
			)
		self.comb += [
			source.eop.eq(sink.eop | no_payload),
			source.data.eq(sink.data),
			source.error.eq(sink.error),
			_decode_header(header_type, self.header, source)
		]
		fsm.act("COPY",
			sink.ack.eq(source.ack),
			source.stb.eq(sink.stb | no_payload),
			If(source.stb &  source.ack & source.eop,
				NextState("IDLE")
			)
		)
