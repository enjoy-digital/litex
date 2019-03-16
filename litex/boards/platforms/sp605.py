# This file is Copyright (c) 2019 Michael Betz <michibetz@gmail.com>
# License: BSD

from litex.build.generic_platform import Pins, IOStandard, Subsignal
from litex.build.xilinx import XilinxPlatform, XC3SProg, iMPACT

_io = [
    # 4 LEDs above PCIE finger
    ("user_led", 0, Pins("D17"), IOStandard("LVCMOS25")),
    ("user_led", 1, Pins("AB4"), IOStandard("LVCMOS25")),
    ("user_led", 2, Pins("D21"), IOStandard("LVCMOS25")),
    ("user_led", 3, Pins("W15"), IOStandard("LVCMOS25")),

    ("user_btn", 0, Pins("F3"), IOStandard("LVCMOS15")),
    ("user_btn", 1, Pins("G6"), IOStandard("LVCMOS15")),
    ("user_btn", 2, Pins("F5"), IOStandard("LVCMOS15")),
    ("user_btn", 3, Pins("C1"), IOStandard("LVCMOS15")),
    ("cpu_reset", 0, Pins("H8"), IOStandard("LVCMOS15")),

    ("serial", 0,
        Subsignal("cts", Pins("F19")),
        Subsignal("rts", Pins("F18")),
        Subsignal("tx", Pins("B21")),
        Subsignal("rx", Pins("H17")),
        IOStandard("LVCMOS25")
    ),

    ("clk200", 0,
        Subsignal("p", Pins("K21"), IOStandard("LVDS_25")),
        Subsignal("n", Pins("K22"), IOStandard("LVDS_25"))
    )
]

_connectors = [
    # t.b.a
]


class Platform(XilinxPlatform):
    default_clk_name = "clk200"
    default_clk_period = 5.0

    def __init__(self, toolchain="ise"):
        XilinxPlatform.__init__(self, "xc6slx45t-fgg484-3", _io, _connectors,
                                toolchain=toolchain)
        # self.toolchain.bitstream_commands = \
        #     ["set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]"]
        # self.toolchain.additional_commands = \
        #     ["write_cfgmem -force -format bin -interface spix4 -size 16 "
        #      "-loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]

    def create_programmer(self, programmer="xc3sprog"):
        if programmer == "xc3sprog":
            return XC3SProg("xpc", p=1)
        elif programmer == "impact":
            return iMPACT()
        else:
            raise ValueError("{} programmer is not supported"
                             .format(programmer))
