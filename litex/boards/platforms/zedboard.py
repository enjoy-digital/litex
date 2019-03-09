# This file is Copyright (c) 2019 Michael Betz <michibetz@gmail.com>
# License: BSD

from litex.build.generic_platform import Pins, IOStandard
from litex.build.xilinx import XilinxPlatform, XC3SProg, VivadoProgrammer
from litex.build.openocd import OpenOCD

_io = [
    # 8 LEDs above DIP switches (Bank 33)
    ("user_led", 0, Pins("T22"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("T21"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("U22"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("U21"), IOStandard("LVCMOS33")),
    ("user_led", 4, Pins("V22"), IOStandard("LVCMOS33")),
    ("user_led", 5, Pins("W22"), IOStandard("LVCMOS33")),
    ("user_led", 6, Pins("U19"), IOStandard("LVCMOS33")),
    ("user_led", 7, Pins("U14"), IOStandard("LVCMOS33")),

    # 8 Switches (Bank 35)
    ("user_sw", 0, Pins("F22"), IOStandard("LVCMOS18")),
    ("user_sw", 1, Pins("G22"), IOStandard("LVCMOS18")),
    ("user_sw", 2, Pins("H22"), IOStandard("LVCMOS18")),
    ("user_sw", 3, Pins("F21"), IOStandard("LVCMOS18")),
    ("user_sw", 4, Pins("H19"), IOStandard("LVCMOS18")),
    ("user_sw", 5, Pins("H18"), IOStandard("LVCMOS18")),
    ("user_sw", 6, Pins("H17"), IOStandard("LVCMOS18")),
    ("user_sw", 7, Pins("M15"), IOStandard("LVCMOS18")),

    # push buttons (Bank 34)
    ("user_btn",   0, Pins("D13"), IOStandard("LVCMOS18")),
    ("user_btn",   1, Pins("C10"), IOStandard("LVCMOS18")),
    ("user_btn_c", 0, Pins("P16"), IOStandard("LVCMOS18")),
    ("user_btn_d", 0, Pins("R16"), IOStandard("LVCMOS18")),
    ("user_btn_l", 0, Pins("N15"), IOStandard("LVCMOS18")),
    ("user_btn_r", 0, Pins("R18"), IOStandard("LVCMOS18")),
    ("user_btn_u", 0, Pins("T18"), IOStandard("LVCMOS18")),

    # Clock source (Bank 13)
    ("clk100", 0, Pins("Y9"), IOStandard("LVCMOS33"))
]


_connectors = [
    # Bank 13
    ("pmoda", "Y11 AA11 Y10 AA9 AB11 AB10 AB9 AA8"),
    ("pmodb", "W12 W11 V10 W8 V12 W10 V9 V8"),
    ("pmodc", "AB6 AB7 AA4 Y4 T6 R6 U4 T4"),
    ("pmodd", "W7 V7 V4 V5 W5 W6 U5 U6"),
    ("XADC", {
        # Bank 34
        "gio_0" : "H15",
        "gio_1" : "R15",
        "gio_2" : "K15",
        "gio_3" : "J15",
        # Bank 35
        "AD0N_R" : "E16",
        "AD0P_R" : "F16",
        "AD8N_N" : "D17",
        "AD8P_R" : "D16"
    }),
]


class Platform(XilinxPlatform):
    default_clk_name = "clk100"
    default_clk_period = 10.0

    def __init__(self, toolchain="vivado"):
        XilinxPlatform.__init__(self, "xc7z020clg484-1", _io, _connectors,
                                toolchain=toolchain)
        # self.toolchain.bitstream_commands = \
        #     ["set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]"]
        # self.toolchain.additional_commands = \
        #     ["write_cfgmem -force -format bin -interface spix4 -size 16 "
        #      "-loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]

    def create_programmer(self, programmer="xc3sprog"):
        if programmer == "xc3sprog":
            return XC3SProg("jtaghs2", jtag_pos=1)
        elif programmer == "openocd":
            return OpenOCD(config="board/digilent_zedboard.cfg")
        elif programmer == "vivado":
            return VivadoProgrammer(flash_part="s25fl256s-3.3v-qspi-x4-single")
        else:
            raise ValueError("{} programmer is not supported"
                             .format(programmer))
