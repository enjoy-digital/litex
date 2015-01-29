from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

class LiteEthIPV4Depacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_mac_description(8),
			eth_ipv4_description(8),
			ipv4_header,
			ipv4_header_len)

class LiteEthIPV4Packetizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_ipv4_description(8),
			eth_mac_description(8),
			ipv4_header,
			ipv4_header_len)
