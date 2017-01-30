from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform, VivadoProgrammer


_io = [
    ("user_led", 0, Pins("AP8"), IOStandard("LVCMOS18")),
    ("user_led", 1, Pins("H23"), IOStandard("LVCMOS18")),
    ("user_led", 2, Pins("P20"), IOStandard("LVCMOS18")),
    ("user_led", 3, Pins("P21"), IOStandard("LVCMOS18")),
    ("user_led", 4, Pins("N22"), IOStandard("LVCMOS18")),
    ("user_led", 5, Pins("M22"), IOStandard("LVCMOS18")),
    ("user_led", 6, Pins("R23"), IOStandard("LVCMOS18")),
    ("user_led", 7, Pins("P23"), IOStandard("LVCMOS18")),

    ("clk125", 0,
        Subsignal("p", Pins("G10"), IOStandard("LVDS")),
        Subsignal("n", Pins("F10"), IOStandard("LVDS"))
    ),

    ("serial", 0,
        Subsignal("cts", Pins("L23")),
        Subsignal("rts", Pins("K27")),
        Subsignal("tx", Pins("K26")),
        Subsignal("rx", Pins("G25")),
        IOStandard("LVCMOS18")
	),
]

class Platform(XilinxPlatform):
    default_clk_name = "clk125"
    default_clk_period = 8.0

    def __init__(self):
        XilinxPlatform.__init__(self, "xcku040-ffva1156-2-e", _io, toolchain="vivado")

    def create_programmer(self):
        return VivadoProgrammer()
