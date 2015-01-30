from liteeth.common import *

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
		###
		shift = Signal()
		header = Signal(header_length*8)
		counter = Counter(max=header_length)
		self.submodules += counter

		self.sync += [
			If(shift,
				header.eq(Cat(header[8:], sink.data))
			)
		]

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			sink.ack.eq(1),
			counter.reset.eq(1),
			If(sink.stb,
				shift.eq(1),
				NextState("RECEIVE_HEADER")
			)
		)
		fsm.act("RECEIVE_HEADER",
			sink.ack.eq(1),
			If(sink.stb,
				counter.ce.eq(1),
				shift.eq(1),
				If(counter.value == header_length-2,
					NextState("COPY")
				)
			)
		)
		self.sync += \
			If(fsm.before_entering("COPY"),
				source.sop.eq(1)
			).Elif(source.stb & source.ack,
				source.sop.eq(0)
			)
		self.comb += [
			source.eop.eq(sink.eop),
			source.data.eq(sink.data),
			source.error.eq(sink.error),
			_decode_header(header_type, header, source)
		]
		fsm.act("COPY",
			sink.ack.eq(source.ack),
			source.stb.eq(sink.stb),
			If(source.stb &  source.ack & source.eop,
				NextState("IDLE")
			)
		)
