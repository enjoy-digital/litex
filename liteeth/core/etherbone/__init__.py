from liteeth.common import *

from liteeth.generic.arbiter import Arbiter
from liteeth.generic.dispatcher import Dispatcher

from liteeth.core.etherbone.packet import *
from liteeth.core.etherbone.probe import *
from liteeth.core.etherbone.record import *

class LiteEthEtherbone(Module):
	def __init__(self, udp, udp_port):
		self.submodules.packet = packet = LiteEthEtherbonePacket(udp, udp_port)
		self.submodules.probe = probe = LiteEthEtherboneProbe()
		self.submodules.record = record = LiteEthEtherboneRecord()

		dispatcher = Dispatcher(packet.source, [probe.sink, record.sink])
		self.comb += dispatcher.sel.eq(~packet.source.pf)
		self.submodules += dispatcher

		arbiter = Arbiter([probe.source, record.source], packet.sink)
		self.submodules += arbiter
