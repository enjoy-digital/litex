from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.lattice.programmer import TinyFpgaBProgrammer

_io = [
    ("usb", 0,
        Subsignal("d_p", Pins("A3")),
        Subsignal("d_n", Pins("A4")),
        IOStandard("LVCMOS33")
    ),

    ("serial", 0,
        Subsignal("tx", Pins("B2")),
        Subsignal("rx", Pins("A2")),
        IOStandard("LVCMOS33")
    ),

    ("spiflash", 0,
        Subsignal("cs_n", Pins("F7"), IOStandard("LVCMOS33")),
        Subsignal("clk", Pins("G7"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("G6"), IOStandard("LVCMOS33")),
        Subsignal("miso", Pins("H7"), IOStandard("LVCMOS33"))
    ),

    ("clk16", 0, Pins("B4"), IOStandard("LVCMOS33"))
]

_connectors = [
    # B2-J1, Pins 4-13
    # D9-C9, Pins 18-19, Pins 21-24
    # E8, Pin 20 (Input only)
    ("GPIO", "B2 A2 A1 B1 C1 D1 E1 G1 H1 J1 D9 C9 A9 A8 A7 A6"),
    ("GBIN", "E8")
]


class Platform(LatticePlatform):
    default_clk_name = "clk16"
    default_clk_period = 62.5

    def __init__(self):
        LatticePlatform.__init__(self, "ice40-lp8k-cm81", _io, _connectors,
                                 toolchain="icestorm")

    def create_programmer(self):
        return TinyFpgaBProgrammer()
