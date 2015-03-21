# This file is Copyright (c) 2015 Matt O'Gorman <mog@rldn.net>
# License: BSD

from mibuild.generic_platform import *
from mibuild.crg import SimpleCRG
from mibuild.xilinx.ise import XilinxISEPlatform
from mibuild.xilinx.programmer import XC3SProg

_io = [
	("user_led", 0, Pins("P11"), IOStandard("LVTTL"), Misc("SLEW=SLOW")),
	("user_led", 1, Pins("N9"),  IOStandard("LVTTL"), Misc("SLEW=SLOW")),
	("user_led", 2, Pins("M9"),  IOStandard("LVTTL"), Misc("SLEW=SLOW")),
	("user_led", 3, Pins("P9"),  IOStandard("LVTTL"), Misc("SLEW=SLOW")),
	("user_led", 4, Pins("T8"),  IOStandard("LVTTL"), Misc("SLEW=SLOW")),
	("user_led", 5, Pins("N8"),  IOStandard("LVTTL"), Misc("SLEW=SLOW")),
	("user_led", 6, Pins("P8"),  IOStandard("LVTTL"), Misc("SLEW=SLOW")),
	("user_led", 7, Pins("P7"),  IOStandard("LVTTL"), Misc("SLEW=SLOW")),

	("user_sw", 0, Pins("L1"), IOStandard("LVTTL"), Misc("PULLUP")),
	("user_sw", 1, Pins("L3"), IOStandard("LVTTL"), Misc("PULLUP")),
	("user_sw", 2, Pins("L4"), IOStandard("LVTTL"), Misc("PULLUP")),
	("user_sw", 3, Pins("L5"), IOStandard("LVTTL"), Misc("PULLUP")),

	("clk32", 0, Pins("J4"), IOStandard("LVCMOS33")),
	("clk50", 0, Pins("K3"), IOStandard("LVCMOS33")),

	("spiflash", 0,
		Subsignal("cs_n", Pins("T3"), IOStandard("LVTTL")),
		Subsignal("clk",  Pins("R11"), IOStandard("LVTTL")),
		Subsignal("mosi", Pins("T10"), IOStandard("LVTTL")),
		Subsignal("miso", Pins("P10"), IOStandard("LVTTL"))
	),

	("adc", 0,
		Subsignal("cs_n", Pins("F6"), IOStandard("LVTTL")),
		Subsignal("clk",  Pins("G6"), IOStandard("LVTTL")),
		Subsignal("mosi", Pins("H4"), IOStandard("LVTTL")),
		Subsignal("miso", Pins("H5"), IOStandard("LVTTL"))
	),

	("serial", 0,
		Subsignal("tx", Pins("N6"), IOStandard("LVTTL")), # FTDI D1
		Subsignal("rx", Pins("M7"), IOStandard("LVTTL"))  # FTDI D0
	),

	("audio", 0,
		Subsignal("a0", Pins("B8"), IOStandard("LVTTL")),
		Subsignal("a1", Pins("A8"), IOStandard("LVTTL"))
	),

	("sdram_clock", 0, Pins("G16"), IOStandard("LVTTL")),
	("sdram", 0,
		Subsignal("a", Pins("T15 R16 P15 P16 N16 M15 M16 L16 K15 K16 R15 J16 H15")),
		Subsignal("dq", Pins("T13 T12 R12 T9 R9 T7 R7 T6 F16 E15 E16 D16 B16 B15 C16 C15")),
		Subsignal("we_n", Pins("R5")),
		Subsignal("ras_n", Pins("R2")),
		Subsignal("cas_n", Pins("T4")),
		Subsignal("cs_n", Pins("R1")),
		Subsignal("cke", Pins("H16")),
		Subsignal("ba", Pins("R14 T14")),
		Subsignal("dm", Pins("T5 F15"))
	),

	("sd", 0,
		Subsignal("sck", Pins("L12")),
		Subsignal("d3", Pins("K12")),
		Subsignal("d", Pins("M10")),
		Subsignal("d1", Pins("L10")),
		Subsignal("d2", Pins("J11")),
		Subsignal("cmd", Pins("K11"))
	),

	("dvi_in", 0,
		Subsignal("clk_p", Pins("C9"), IOStandard("TMDS_33")),
		Subsignal("clk_n", Pins("A9"), IOStandard("TMDS_33")),
		Subsignal("data_p", Pins("C7 B6 B5"), IOStandard("TMDS_33")),
		Subsignal("data_n", Pins("A7 A6 A5"), IOStandard("TMDS_33")),
		Subsignal("scl", Pins("C1"), IOStandard("LVTTL")),
		Subsignal("sda", Pins("B1"), IOStandard("LVTTL"))
	),

	("dvi_out", 0,
		Subsignal("clk_p", Pins("B14"), IOStandard("TMDS_33")),
		Subsignal("clk_n", Pins("A14"), IOStandard("TMDS_33")),
		Subsignal("data_p", Pins("C13 B12 C11"), IOStandard("TMDS_33")),
		Subsignal("data_n", Pins("A13 A12 A11"), IOStandard("TMDS_33")),
	)
]

_connectors = [
	("A", "E7 C8 D8 E8 D9 A10 B10 C10 E10 F9 F10 D11"),
	("B", "E11 D14 D12 E12 E13 F13 F12 F14 G12 H14 J14"),
	("C", "J13 J12 K14 L14 L13 M14 M13 N14 M12 N12 P12 M11"),
	("D", "D6 C6 E6 C5"),
	("E", "D5 A4 G5 A3 B3 A2 B2 C3 C2 D3 D1 E3"),
	("F", "E2 E1 E4 F4 F5 G3 F3 G1 H3 H1 H2 J1")
]

class Platform(XilinxISEPlatform):
	default_clk_name = "clk50"
	default_clk_period = 20
	def __init__(self):
		XilinxISEPlatform.__init__(self, "xc6slx9-3-ftg256", _io,
			lambda p: SimpleCRG(p, "clk50", None), _connectors)

	def create_programmer(self):
		return XC3SProg("minispartan6", "bscan_spi_minispartan6.bit")

	def do_finalize(self, fragment):
		try:
			self.add_period_constraint(self.lookup_request("50"), 50)
		except ConstraintError:
			pass