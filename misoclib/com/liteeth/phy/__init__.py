from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.generic import *

from misoclib.com.liteeth.phy.sim import LiteEthPHYSim
from misoclib.com.liteeth.phy.mii import LiteEthPHYMII
from misoclib.com.liteeth.phy.gmii import LiteEthPHYGMII

def LiteEthPHY(clock_pads, pads, **kwargs):
	# Autodetect PHY
	if hasattr(pads, "source_stb"):
		return LiteEthPHYSim(pads)
	elif hasattr(clock_pads, "gtx") and flen(pads.tx_data) == 8:
		return LiteEthPHYGMII(clock_pads, pads, **kwargs)
	elif flen(pads.tx_data) == 4:
		return LiteEthPHYMII(clock_pads, pads, **kwargs)
	else:
		raise ValueError("Unable to autodetect PHY from platform file, use direct instanciation")
