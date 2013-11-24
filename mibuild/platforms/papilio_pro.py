from mibuild.generic_platform import *
from mibuild.xilinx_ise import XilinxISEPlatform, CRG_SE

_io = [
	("user_led", 0, Pins("P112"), IOStandard("LVCMOS33"), Drive(24), Misc("SLEW=QUIETIO")),

	("user_btn", 0, Pins("P114"), IOStandard("LVCMOS33")), # C0
	("user_btn", 1, Pins("P115"), IOStandard("LVCMOS33")), # C1

	("clk32", 0, Pins("P94"), IOStandard("LVCMOS33")),

	("serial", 0,
		Subsignal("tx", Pins("P105"), IOStandard("LVCMOS33"), Misc("SLEW=SLOW")),
		Subsignal("rx", Pins("P101"), IOStandard("LVCMOS33"), Misc("PULLUP"))
	),

	("spiflash", 0,
		Subsignal("cs", Pins("P38")),
		Subsignal("clk", Pins("P70")),
		Subsignal("mosi", Pins("P64")),
		Subsignal("miso", Pins("P65"), Misc("PULLUP")),
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
	),
]

class Platform(XilinxISEPlatform):
	def __init__(self):
		XilinxISEPlatform.__init__(self, "xc6slx9-tqg144-2", _io,
			lambda p: CRG_SE(p, "clk32", None))

	def do_finalize(self, fragment):
		try:
			self.add_platform_command("""
NET "{clk32}" TNM_NET = "GRPclk32";
TIMESPEC "TSclk32" = PERIOD "GRPclk32" 31.25 ns HIGH 50%;
""", clk32=self.lookup_request("clk32"))
		except ConstraintError:
			pass
