# This file is Copyright (c) 2015 Matt O'Gorman <mog@rldn.net>
# License: BSD

from migen.build.generic_platform import *
from migen.build.xilinx import XilinxPlatform
from migen.build.xilinx.programmer import XC3SProg, FpgaProg


_io = [
    ("user_led", 0, Pins("P11"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("N9"),  IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("M9"),  IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("P9"),  IOStandard("LVCMOS33")),
    ("user_led", 4, Pins("T8"),  IOStandard("LVCMOS33")),
    ("user_led", 5, Pins("N8"),  IOStandard("LVCMOS33")),
    ("user_led", 6, Pins("P8"),  IOStandard("LVCMOS33")),
    ("user_led", 7, Pins("P7"),  IOStandard("LVCMOS33")),

    ("user_sw", 0, Pins("L1"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_sw", 1, Pins("L3"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_sw", 2, Pins("L4"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_sw", 3, Pins("L5"), IOStandard("LVCMOS33"), Misc("PULLUP")),

    ("clk32", 0, Pins("J4"), IOStandard("LVCMOS33")),
    ("clk50", 0, Pins("K3"), IOStandard("LVCMOS33")),

    ("spiflash", 0,
        Subsignal("cs_n", Pins("T3"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("R11"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("T10"), IOStandard("LVCMOS33")),
        Subsignal("miso", Pins("P10"), IOStandard("LVCMOS33"))
    ),

    ("adc", 0,
        Subsignal("cs_n", Pins("F6"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("G6"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("H4"), IOStandard("LVCMOS33")),
        Subsignal("miso", Pins("H5"), IOStandard("LVCMOS33"))
    ),

    ("serial", 0,
        Subsignal("tx", Pins("N6"), IOStandard("LVCMOS33")),  # FTDI D1
        Subsignal("rx", Pins("M7"), IOStandard("LVCMOS33"))   # FTDI D0
    ),

    ("audio", 0,
        Subsignal("a0", Pins("B8"), IOStandard("LVCMOS33")),
        Subsignal("a1", Pins("A8"), IOStandard("LVCMOS33"))
    ),

    ("sdram_clock", 0, Pins("G16"), IOStandard("LVCMOS33"), Misc("SLEW=FAST")),
    ("sdram", 0,
        Subsignal("a", Pins("T15 R16 P15 P16 N16 M15 M16 L16 K15 K16 R15 J16 H15")),
        Subsignal("dq", Pins("T13 T12 R12 T9 R9 T7 R7 T6 F16 E15 E16 D16 B16 B15 C16 C15")),
        Subsignal("we_n", Pins("R5")),
        Subsignal("ras_n", Pins("R2")),
        Subsignal("cas_n", Pins("T4")),
        Subsignal("cs_n", Pins("R1")),
        Subsignal("cke", Pins("H16")),
        Subsignal("ba", Pins("R14 T14")),
        Subsignal("dm", Pins("T5 F15")),
        IOStandard("LVCMOS33"), Misc("SLEW=FAST")
    ),

    ("usb_fifo", 0,
        Subsignal("data", Pins("M7 N6 M6 P5 N5 P4 P2 P1")),
        Subsignal("rxf_n", Pins("N3")),
        Subsignal("txe_n", Pins("N1")),
        Subsignal("rd_n", Pins("M1")),
        Subsignal("wr_n", Pins("M2")),
        Subsignal("siwua", Pins("M3")),
        IOStandard("LVCMOS33"), Drive(8), Misc("SLEW=FAST")
    ),

    ("sd", 0,
        Subsignal("sck", Pins("L12")),
        Subsignal("d3", Pins("K12")),
        Subsignal("d", Pins("M10")),
        Subsignal("d1", Pins("L10")),
        Subsignal("d2", Pins("J11")),
        Subsignal("cmd", Pins("K11")),
        IOStandard("LVCMOS33")
    ),

    ("dvi_in", 0,
        Subsignal("clk_p", Pins("C9"), IOStandard("TMDS_33")),
        Subsignal("clk_n", Pins("A9"), IOStandard("TMDS_33")),
        Subsignal("data_p", Pins("C7 B6 B5"), IOStandard("TMDS_33")),
        Subsignal("data_n", Pins("A7 A6 A5"), IOStandard("TMDS_33")),
        Subsignal("scl", Pins("C1"), IOStandard("LVCMOS33")),
        Subsignal("sda", Pins("B1"), IOStandard("LVCMOS33"))
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


class Platform(XilinxPlatform):
    default_clk_name = "clk32"
    default_clk_period = 31.25

    def __init__(self, device="xc6slx9", programmer="xc3sprog"):
        self.programmer = programmer
        XilinxPlatform.__init__(self, device+"-3-ftg256", _io, _connectors)

    def create_programmer(self):
        if self.programmer == "xc3sprog":
            return XC3SProg("minispartan6", "bscan_spi_minispartan6.bit")
        elif self.programmer == "fpgaprog":
            return FpgaProg()
        else:
            raise ValueError("{} programmer is not supported".format(programmer))
