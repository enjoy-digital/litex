from liteeth.common import *
from liteeth.core.etherbone import common
from liteeth.core.etherbone.packet import *

class LiteEthEtherbone(Module):
	def __init__(self, udp, udp_port):
		self.submodules.packet = packet = LiteEthEtherbonePacket(udp, udp_port)

		self.submodules.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			packet.source.ack.eq(1),
			If(packet.source.stb & packet.source.sop,
				If(packet.source.pf,
					packet.source.ack.eq(0),
					NextState("SEND_PROBE_RESPONSE")
				)
			)
		)
		fsm.act("SEND_PROBE_RESPONSE",
			packet.sink.stb.eq(1),
			packet.sink.sop.eq(1),
			packet.sink.eop.eq(1),
			packet.sink.pr.eq(1),
			packet.sink.ip_address.eq(packet.source.ip_address),
			packet.sink.length.eq(0),
			If(packet.sink.ack,
				packet.source.ack.eq(1),
				NextState("IDLE")
			)
		)
