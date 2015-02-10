from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

class LiteEthEtherboneDepacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_udp_user_description(32),
			eth_etherbone_description(32),
			etherbone_header,
			etherbone_header_len)

class LiteEthEtherbonePacketizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_etherbone_description(32),
			eth_udp_user_description(32),
			etherbone_header,
			etherbone_header_len)
