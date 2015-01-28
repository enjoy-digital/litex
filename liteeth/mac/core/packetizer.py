from liteeth.common import *

def _encode_header(h_dict, h_signal, obj):
	r = []
	for k, v in sorted(h_dict.items()):
		start = v.word*32+v.offset
		end = start+v.width
		r.append(h_signal[start:end].eq(getattr(obj, k)))
	return r

class LiteEthMACPacketizer(Module):
	def __init__(self):
		self.sink = sink = Sink(eth_phy_description(8))
		self.source = source = Source(eth_mac_description(8))
		###
		header = Signal(mac_header_length*8)
		header_reg = Signal(mac_header_length*8)
		load = Signal()
		shift = Signal()
		counter = Counter(max=mac_header_length)
		self.submodules += counter

		self.comb += header.eq(_encode_header(mac_header, header, sink))
		self.sync += [
			If(load,
				header_reg.eq(header)
			).Elif(shift,
				header_reg.eq(Cat(header_reg[8:], Signal(8)))
			)
		]

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			sink.ack.eq(1),
			If(sink.stb & sink.sop,
				load.eq(1),
				sink.ack.eq(0),
				source.stb.eq(1),
				source.sop.eq(1),
				source.eop.eq(0),
				source.data.eq(header[:8]),
				If(source.stb & source.ack,
					NextState("SEND_HEADER"),
				)
			)
		)
		fsm.act("SEND_HEADER",
			source.stb.eq(1),
			source.sop.eq(0),
			source.eop.eq(sink.eop),
			source.data.eq(header_reg[8:16]),
			If(source.stb & source.ack,
				sink.ack.eq(1),
				If(counter == mac_header_length-2,
					NextState("COPY")
				)
			)
		)
		fsm.act("COPY",
			source.stb.eq(sink.stb),
			source.sop.eq(0),
			source.eop.eq(sink_eop),
			source.data.eq(sink.data),
			source.error.eq(sink.error),
			If(source.stb & source.ack,
				sink.ack.eq(1),
				If(source.eop,
					NextState("IDLE")
				)
			)
		)
