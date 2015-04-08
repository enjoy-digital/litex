from mibuild.generic_platform import *
from mibuild.xilinx.platform import XilinxPlatform

_io = [
	("sys_clk", 0, Pins("X")),
	("sys_rst", 1, Pins("X")),

	("sata", 0,
		Subsignal("refclk_p", Pins("C8")),
		Subsignal("refclk_n", Pins("C7")),
		Subsignal("txp", Pins("D2")),
		Subsignal("txn", Pins("D1")),
		Subsignal("rxp", Pins("E4")),
		Subsignal("rxn", Pins("E3")),
	),
]

class Platform(XilinxPlatform):
	def __init__(self, device="xc7k325t", programmer=""):
		XilinxPlatform.__init__(self, device, _io)

	def do_finalize(self, *args, **kwargs):
		pass
