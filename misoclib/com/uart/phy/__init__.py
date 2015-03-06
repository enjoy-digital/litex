from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.generic import *

from misoclib.com.uart.phy.sim import UARTPHYSim
from misoclib.com.uart.phy.serial import UARTPHYSerial

def UARTPHY(pads, *args, **kwargs):
	# Autodetect PHY
	if hasattr(pads, "source_stb"):
		return UARTPHYSim(pads, *args, **kwargs)
	else:
		return UARTPHYSerial(pads, *args, **kwargs)
