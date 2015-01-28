import math

from liteeth.common import *

def _decode_header(h_dict, h_signal, obj):
	r = []
	for k, v in sorted(h_dict.items()):
		start = v.byte*8+v.offset
		end = start+v.width
		r.append(getattr(obj, k).eq(h_signal[start:end]))
	return r

class LiteEthMACDepacketizer(Module):
	def __init__(self):
		self.sink = sink = Sink(eth_mac_description(8))
		self.source = source = Source(eth_phy_description(8))
		###
		shift = Signal()
		header = Signal(mac_header_length*8)
		counter = Counter(max=mac_header_length)
		self.submodules += counter

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
				If(counter.value == mac_header_length-2,
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
			source.sop.eq(sop),
			source.eop.eq(sink.eop),
			source.data.eq(sink.data),
			source.error.eq(sink.error),
			_decode_header(mac_header, header, source)
		]
		fsm.act("COPY",
			sink.ack.eq(source.ack),
			source.stb.eq(sink.stb),
			If(source.stb &  source.ack & source.eop,
				NextState("IDLE")
			)
		)
