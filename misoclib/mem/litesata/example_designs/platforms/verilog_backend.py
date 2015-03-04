from mibuild.generic_platform import *
from mibuild.xilinx.common import CRG_DS
from mibuild.xilinx.vivado import XilinxVivadoPlatform

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

class Platform(XilinxVivadoPlatform):
	def __init__(self, crg_factory=lambda p: CRG_DS(p, "clk200", "cpu_reset"), **kwargs):
		XilinxVivadoPlatform.__init__(self, "xc7k325t-ffg900-2", _io, crg_factory)

	def do_finalize(self, *args, **kwargs):
		pass
