from mibuild.generic_platform import *
from mibuild.crg import SimpleCRG
from mibuild.xilinx.ise import XilinxISEPlatform
from mibuild.xilinx.programmer import XC3SProg

_io = [
	("user_led", 0, Pins("P112"), IOStandard("LVCMOS33"), Drive(24), Misc("SLEW=QUIETIO")),

	("clk32", 0, Pins("P94"), IOStandard("LVCMOS33")),

	("serial", 0,
		Subsignal("tx", Pins("P105"), IOStandard("LVCMOS33"), Misc("SLEW=SLOW")),
		Subsignal("rx", Pins("P101"), IOStandard("LVCMOS33"), Misc("PULLUP"))
	),

	("spiflash", 0,
		Subsignal("cs_n", Pins("P38")),
		Subsignal("clk", Pins("P70")),
		Subsignal("mosi", Pins("P64")),
		Subsignal("miso", Pins("P65"), Misc("PULLUP")),
		IOStandard("LVCMOS33"), Misc("SLEW=FAST")
	),
	("spiflash2x", 0,
		Subsignal("cs_n", Pins("P38")),
		Subsignal("clk", Pins("P70")),
		Subsignal("dq", Pins("P64", "P65")),
		IOStandard("LVCMOS33"), Misc("SLEW=FAST")
	),

	("sdram_clock", 0, Pins("P32"), IOStandard("LVCMOS33"), Misc("SLEW=FAST")),
	("sdram", 0,
		Subsignal("a", Pins("P140 P139 P138 P137 P46 P45 P44",
		  "P43 P41 P40 P141 P35 P34")),
		Subsignal("ba", Pins("P143 P142")),
		Subsignal("cs_n", Pins("P1")),
		Subsignal("cke", Pins("P33")),
		Subsignal("ras_n", Pins("P2")),
		Subsignal("cas_n", Pins("P5")),
		Subsignal("we_n", Pins("P6")),
		Subsignal("dq", Pins("P9 P10 P11 P12 P14 P15 P16 P8 P21 P22 P23 P24 P26 P27 P29 P30")),
		Subsignal("dm", Pins("P7 P17")),
		IOStandard("LVCMOS33"), Misc("SLEW=FAST")
	)
]

_connectors = [
	("A", "P48 P51 P56 P58 P61 P66 P67 P75 P79 P81 P83 P85 P88 P93 P98 P100"),
	("B", "P99 P97 P92 P87 P84 P82 P80 P78 P74 P95 P62 P59 P57 P55 P50 P47"),
	("C", "P114 P115 P116 P117 P118 P119 P120 P121 P123 P124 P126 P127 P131 P132 P133 P134")
]

class Platform(XilinxISEPlatform):
	identifier = 0x5050
	default_clk_name = "clk32"
	default_clk_period = 31.25
	def __init__(self):
		XilinxISEPlatform.__init__(self, "xc6slx9-tqg144-2", _io,
			lambda p: SimpleCRG(p, "clk32", None), _connectors)

	def create_programmer(self):
		return XC3SProg("papilio", "bscan_spi_lx9_papilio.bit")

	def do_finalize(self, fragment):
		try:
			self.add_period_constraint(self.lookup_request("clk32"), 31.25)
		except ConstraintError:
			pass
