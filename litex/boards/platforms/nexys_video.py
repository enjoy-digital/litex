# This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform, XC3SProg, VivadoProgrammer

_io = [
    ("user_led", 0, Pins("T14"), IOStandard("LVCMOS25")),
    ("user_led", 1, Pins("T15"), IOStandard("LVCMOS25")),
    ("user_led", 2, Pins("T16"), IOStandard("LVCMOS25")),
    ("user_led", 3, Pins("U16"), IOStandard("LVCMOS25")),
    ("user_led", 4, Pins("V15"), IOStandard("LVCMOS25")),
    ("user_led", 5, Pins("W16"), IOStandard("LVCMOS25")),
    ("user_led", 6, Pins("W15"), IOStandard("LVCMOS25")),
    ("user_led", 7, Pins("Y13"), IOStandard("LVCMOS25")),

    ("user_sw", 0, Pins("E22"), IOStandard("LVCMOS12")),
    ("user_sw", 1, Pins("F21"), IOStandard("LVCMOS12")),
    ("user_sw", 2, Pins("G21"), IOStandard("LVCMOS12")),
    ("user_sw", 3, Pins("G22"), IOStandard("LVCMOS12")),
    ("user_sw", 4, Pins("H17"), IOStandard("LVCMOS12")),
    ("user_sw", 5, Pins("J16"), IOStandard("LVCMOS12")),
    ("user_sw", 6, Pins("K13"), IOStandard("LVCMOS12")),
    ("user_sw", 7, Pins("M17"), IOStandard("LVCMOS12")),


    ("user_btn", 0, Pins("B22"), IOStandard("LVCMOS12")),
    ("user_btn", 1, Pins("D22"), IOStandard("LVCMOS12")),
    ("user_btn", 2, Pins("C22"), IOStandard("LVCMOS12")),
    ("user_btn", 3, Pins("D14"), IOStandard("LVCMOS12")),
    ("user_btn", 4, Pins("F15"), IOStandard("LVCMOS12")),
    ("user_btn", 5, Pins("G4"),  IOStandard("LVCMOS12")),

    ("oled", 0,
        Subsignal("dc",   Pins("W22")),
        Subsignal("res",  Pins("U21")),
        Subsignal("sclk", Pins("W21")),
        Subsignal("sdin", Pins("Y22")),
        Subsignal("vbat", Pins("P20")),
        Subsignal("vdd",  Pins("V22")),
        IOStandard("LVCMOS33")
    ),

    ("clk100", 0, Pins("R4"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("tx", Pins("AA19")),
        Subsignal("rx", Pins("V18")),
        IOStandard("LVCMOS33"),
    )
]


class Platform(XilinxPlatform):
    default_clk_name = "clk100"
    default_clk_period = 10.0

    def __init__(self, toolchain="vivado", programmer="vivado"):
        XilinxPlatform.__init__(self, "xc7a200t-sbg484-1", _io,
                                toolchain=toolchain)
        self.toolchain.bitstream_commands = \
            ["set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]"]
        self.toolchain.additional_commands = \
            ["write_cfgmem -force -format bin -interface spix4 -size 16 "
             "-loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]
        self.programmer = programmer
        self.add_platform_command("set_property INTERNAL_VREF 0.675 [get_iobanks 34]")

    def create_programmer(self):
        if self.programmer == "xc3sprog":
            return XC3SProg("nexys4")
        elif self.programmer == "vivado":
            return VivadoProgrammer(flash_part="n25q128-3.3v-spi-x1_x2_x4")
        else:
            raise ValueError("{} programmer is not supported"
                             .format(self.programmer))
