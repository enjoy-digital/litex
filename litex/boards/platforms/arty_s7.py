# This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# License: BSD

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform, XC3SProg, VivadoProgrammer

_io = [
    ("user_led", 0, Pins("E18"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("F13"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("E13"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("H15"), IOStandard("LVCMOS33")),

    ("rgb_led", 0,
        Subsignal("r", Pins("J15")),
        Subsignal("g", Pins("G17")),
        Subsignal("b", Pins("F15")),
        IOStandard("LVCMOS33")
    ),

    ("rgb_led", 1,
        Subsignal("r", Pins("E15")),
        Subsignal("g", Pins("F18")),
        Subsignal("b", Pins("E14")),
        IOStandard("LVCMOS33")
    ),

    ("user_sw", 0, Pins("H14"), IOStandard("LVCMOS33")),
    ("user_sw", 1, Pins("H18"), IOStandard("LVCMOS33")),
    ("user_sw", 2, Pins("G18"), IOStandard("LVCMOS33")),
    ("user_sw", 3, Pins("M5"), IOStandard("LVCMOS33")),

    ("user_btn", 0, Pins("G15"), IOStandard("LVCMOS33")),
    ("user_btn", 1, Pins("K16"), IOStandard("LVCMOS33")),
    ("user_btn", 2, Pins("J16"), IOStandard("LVCMOS33")),
    ("user_btn", 3, Pins("H13"), IOStandard("LVCMOS33")),

    ("clk100", 0, Pins("R2"), IOStandard("SSTL135")),

    ("cpu_reset", 0, Pins("C18"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("tx", Pins("R12")),
        Subsignal("rx", Pins("V12")),
        IOStandard("LVCMOS33")),

    ("spi", 0,
        Subsignal("clk", Pins("G16")),
        Subsignal("cs_n", Pins("H16")),
        Subsignal("mosi", Pins("H17")),
        Subsignal("miso", Pins("K14")),
        IOStandard("LVCMOS33")
    ),

    ("spiflash4x", 0,  # clock needs to be accessed through STARTUPE2
        Subsignal("cs_n", Pins("M13")),
        Subsignal("dq", Pins("K17", "K18", "L14", "M15")),
        IOStandard("LVCMOS33")
    ),
    ("spiflash", 0,  # clock needs to be accessed through STARTUPE2
        Subsignal("cs_n", Pins("M13")),
        Subsignal("mosi", Pins("K17")),
        Subsignal("miso", Pins("K18")),
        Subsignal("wp", Pins("L14")),
        Subsignal("hold", Pins("M15")),
        IOStandard("LVCMOS33")
    ),

    ("ddram", 0,
        Subsignal("a", Pins(
            "U2 R4 V2 V4 T3 R7 V6 T6",
            "U7 V7 P6 T5 R6 U6"),
            IOStandard("SSTL135")),
        Subsignal("ba", Pins("V5 T1 U3"), IOStandard("SSTL135")),
        Subsignal("ras_n", Pins("U1"), IOStandard("SSTL135")),
        Subsignal("cas_n", Pins("V3"), IOStandard("SSTL135")),
        Subsignal("we_n", Pins("P7"), IOStandard("SSTL135")),
        Subsignal("cs_n", Pins("R3"), IOStandard("SSTL135")),
        Subsignal("dm", Pins("K4 M3"), IOStandard("SSTL135")),
        Subsignal("dq", Pins(
            "K2 K3 L4 M6 K6 M4 L5 L6",
            "N4 R1 N1 N5 M2 P1 M1 P2"),
            IOStandard("SSTL135"),
            Misc("IN_TERM=UNTUNED_SPLIT_40")),
        Subsignal("dqs_p", Pins("K1 N3"), IOStandard("DIFF_SSTL135")),
        Subsignal("dqs_n", Pins("L1 N2"), IOStandard("DIFF_SSTL135")),
        Subsignal("clk_p", Pins("R5"), IOStandard("DIFF_SSTL135")),
        Subsignal("clk_n", Pins("T4"), IOStandard("DIFF_SSTL135")),
        Subsignal("cke", Pins("T2"), IOStandard("SSTL135")),
        Subsignal("odt", Pins("P5"), IOStandard("SSTL135")),
        Subsignal("reset_n", Pins("J6"), IOStandard("SSTL135")),
        Misc("SLEW=FAST"),
    ),

]

_connectors = [
    ("pmoda", "L17 L18 M14 N14 M16 M17 M18 N18"),
    ("pmodb", "P17 P18 R18 T18 P14 P15 N15 P16"),
    ("pmodc", "U15 V16 U17 U18 U16 P13 R13 V14"),
    ("pmodd", "V15 U12 V13 T12 T13 R11 T11 U11")
]

class Platform(XilinxPlatform):
    default_clk_name = "clk100"
    default_clk_period = 10.0

    def __init__(self, toolchain="vivado", programmer="vivado"):
        XilinxPlatform.__init__(self, "xc7s50csga324-1", _io, _connectors,
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
