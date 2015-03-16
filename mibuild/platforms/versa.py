# This file is Copyright (c) 2013 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from mibuild.generic_platform import *
from mibuild.lattice import LatticePlatform
from mibuild.lattice.programmer import LatticeProgrammer

_io = [
	("clk100", 0, Pins("L5"), IOStandard("LVDS25")),

	("user_led", 0, Pins("Y20"), IOStandard("LVCMOS33")),
	("user_led", 1, Pins("AA21"), IOStandard("LVCMOS33")),
	("user_led", 2, Pins("U18"), IOStandard("LVCMOS33")),
	("user_led", 3, Pins("U19"), IOStandard("LVCMOS33")),
	("user_led", 4, Pins("W19"), IOStandard("LVCMOS33")),
	("user_led", 5, Pins("V19"), IOStandard("LVCMOS33")),
	("user_led", 6, Pins("AB20"), IOStandard("LVCMOS33")),
	("user_led", 7, Pins("AA20"), IOStandard("LVCMOS33")),

	("serial", 0,
		Subsignal("tx", Pins("B11"), IOStandard("LVCMOS33")), # X4 IO0
		Subsignal("rx", Pins("B12"), IOStandard("LVCMOS33")), # X4 IO1
	),
]

class Platform(LatticePlatform):
	default_clk_name = "clk100"
	default_clk_period = 10

	def __init__(self):
		LatticePlatform.__init__(self, "LFE3-35EA-6FN484C", _io)

	def create_programmer(self):
		return LatticeProgrammer()
