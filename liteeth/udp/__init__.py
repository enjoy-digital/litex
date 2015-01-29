from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer

class LiteEthUDPDepacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_ipv4_description(8),
			eth_udp_description(8),
			udp_header,
			udp_header_len)

class LiteEthUDPPacketizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_udp_description(8),
			eth_ipv4_description(8),
			udp_header,
			udp_header_len)
