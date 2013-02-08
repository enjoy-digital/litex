from mibuild.generic_platform import *
from mibuild.xilinx_ise import XilinxISEPlatform, CRG_SE

_io = [
	("user_led", 0, Pins("B16"), IOStandard("LVCMOS33"), Drive(24), Misc("SLEW=QUIETIO")),
	("user_led", 1, Pins("A16"), IOStandard("LVCMOS33"), Drive(24), Misc("SLEW=QUIETIO")),

	("user_btn", 0, Pins("AB4"), IOStandard("LVCMOS33")),
	("user_btn", 1, Pins("AA4"), IOStandard("LVCMOS33")),
	("user_btn", 2, Pins("AB5"), IOStandard("LVCMOS33")),
	
	("clk50", 0, Pins("AB11"), IOStandard("LVCMOS33")),

	# When executing softcore code in-place from the flash, we want
	# the flash reset to be released before the system reset.
	("norflash_reset", 0, Pins("P22"), IOStandard("LVCMOS33"), Misc("SLEW=FAST"), Drive(8)),
	("norflash", 0,
		Subsignal("adr", Pins("L22", "L20", "K22", "K21", "J19", "H20", "F22",
			"F21", "K17", "J17", "E22", "E20", "H18", "H19", "F20",
			"G19", "C22", "C20", "D22", "D21", "F19", "F18", "D20", "D19")),
		Subsignal("d", Pins("AA20", "U14", "U13", "AA6", "AB6", "W4", "Y4", "Y7",
			"AA2", "AB2", "V15", "AA18", "AB18", "Y13", "AA12", "AB12"), Misc("PULLDOWN")),
		Subsignal("oe_n", Pins("M22")),
		Subsignal("we_n", Pins("N20")),
		Subsignal("ce_n", Pins("M21")),
		IOStandard("LVCMOS33"), Misc("SLEW=FAST"), Drive(8)
	),
	
	("serial", 0,
		Subsignal("tx", IOStandard("LVCMOS33"), Misc("SLEW=SLOW")),
		Subsignal("rx", IOStandard("LVCMOS33"), Misc("PULLUP"))
	),
	

	("ddram_clock", 0,
		Subsignal("p", Pins("M3")),
		Subsignal("n", Pins("L4")),
		IOStandard("SSTL2_I")
	),	
	("ddram", 0,
		Subsignal("a", Pins("B1", "B2", "H8", "J7", "E4", "D5", "K7", "F5",
			"G6", "C1", "C3", "D1", "D2")),
		Subsignal("ba", Pins("A2", "E6")),
		Subsignal("cs_n", Pins("F7")),
		Subsignal("cke", Pins("G7")),
		Subsignal("ras_n", Pins("E5")),
		Subsignal("cas_n", Pins("C4")),
		Subsignal("we_n", Pins("D3")),
		Subsignal("dq", Pins("Y2", "W3", "W1", "P8", "P7", "P6", "P5", "T4", "T3",
			"U4", "V3", "N6", "N7", "M7", "M8", "R4", "P4", "M6", "L6", "P3", "N4",
			"M5", "V2", "V1", "U3", "U1", "T2", "T1", "R3", "R1", "P2", "P1")),
		Subsignal("dm", Pins("E1", "E3", "F3", "G4")),
		Subsignal("dqs", Pins("F1", "F2", "H5", "H6")),
		IOStandard("SSTL2_I")
	),

	("eth_clocks", 0,
		Subsignal("phy", Pins("M20")),
		Subsignal("rx", Pins("H22")),
		Subsignal("tx", Pins("H21")),
		IOStandard("LVCMOS33")
	),
	("eth", 0,
		Subsignal("rst_n", Pins("R22")),
		Subsignal("dv", Pins("V21")),
		Subsignal("rx_er", Pins("V22")),
		Subsignal("rx_data", Pins("U22", "U20", "T22", "T21")),
		Subsignal("tx_en", Pins("N19")),
		Subsignal("tx_er", Pins("M19")),
		Subsignal("tx_data", Pins("M16", "L15", "P19", "P20")),
		Subsignal("col", Pins("W20")),
		Subsignal("crs", Pins("W22")),
		IOStandard("LVCMOS33")
	),

	("vga_clock", 0, Pins("A11"), IOStandard("LVCMOS33")),
	("vga", 0,
		Subsignal("r", Pins("C6", "B6", "A6", "C7", "A7", "B8", "A8", "D9")),
		Subsignal("g", Pins("C8", "C9", "A9", "D7", "D8", "D10", "C10", "B10")),
		Subsignal("b", Pins("D11", "C12", "B12", "A12", "C13", "A13", "D14", "C14")),
		Subsignal("hsync_n", Pins("A14")),
		Subsignal("vsync_n", Pins("C15")),
		Subsignal("psave_n", Pins("B14")),
		IOStandard("LVCMOS33")
	),
]

class Platform(XilinxISEPlatform):
	def __init__(self):
		XilinxISEPlatform.__init__(self, "xc6slx45-fgg484-2", _io,
			lambda p: CRG_SE(p, "clk50", "user_btn", 20.0))
