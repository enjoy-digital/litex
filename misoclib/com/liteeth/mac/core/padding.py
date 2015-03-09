from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.generic import *

class LiteEthMACPaddingInserter(Module):
	def __init__(self, dw, packet_min_length):
		self.sink = sink = Sink(eth_phy_description(dw))
		self.source = source = Source(eth_phy_description(dw))
		###
		packet_min_data = math.ceil(packet_min_length/(dw/8))

		self.submodules.counter = counter = Counter(max=eth_mtu)

		self.submodules.fsm = fsm = FSM(reset_state="COPY")
		fsm.act("COPY",
			counter.reset.eq(sink.stb & sink.sop),
			Record.connect(sink, source),
			If(sink.stb & sink.ack,
				counter.ce.eq(1),
				If(sink.eop,
					If(counter.value < packet_min_data,
						source.eop.eq(0),
						NextState("PADDING")
					)
				)
			)
		)
		fsm.act("PADDING",
			source.stb.eq(1),
			source.eop.eq(counter.value == packet_min_data),
			source.data.eq(0),
			If(source.ack,
				counter.ce.eq(1),
				If(source.eop,
					NextState("COPY")
				)
			)
		)

class LiteEthMACPaddingChecker(Module):
	def __init__(self, dw, packet_min_length):
		self.sink = sink = Sink(eth_phy_description(dw))
		self.source = source = Source(eth_phy_description(dw))
		###
		# XXX see if we should drop the packet when
		# payload size < minimum ethernet payload size
		self.comb += Record.connect(sink, source)

