from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.generic import *

def LiteEthPHY(clock_pads, pads, **kwargs):
	# Autodetect PHY
	if hasattr(pads, "source_stb"):
		from misoclib.com.liteeth.phy.sim import LiteEthPHYSim
		return LiteEthPHYSim(pads)
	elif hasattr(clock_pads, "gtx") and flen(pads.tx_data) == 8:
		from misoclib.com.liteeth.phy.gmii import LiteEthPHYGMII
		return LiteEthPHYGMII(clock_pads, pads, **kwargs)
	elif flen(pads.tx_data) == 4:
		from misoclib.com.liteeth.phy.mii import LiteEthPHYMII
		return LiteEthPHYMII(clock_pads, pads, **kwargs)
	else:
		raise ValueError("Unable to autodetect PHY from platform file, use direct instantiation")
