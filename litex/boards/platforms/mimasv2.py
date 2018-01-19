from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform


_io = [
    ("clk100", 0, Pins("V10"), IOStandard("LVCMOS33")),
    ("clk12", 0, Pins("D9"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("tx", Pins("B8"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),
        Subsignal("rx", Pins("A8"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST"))),

    ("spiflash", 0,
        Subsignal("cs_n", Pins("V3")),
        Subsignal("clk", Pins("R15")),
        Subsignal("mosi", Pins("T13")),
        Subsignal("miso", Pins("R13"), Misc("PULLUP")),
        IOStandard("LVCMOS33"), Misc("SLEW=FAST")),

    ("ddram_clock", 0,
        Subsignal("p", Pins("G3")),
        Subsignal("n", Pins("G1")),
        IOStandard("MOBILE_DDR")),

    ("ddram", 0,
        Subsignal("a", Pins("J7 J6 H5 L7 F3 H4 H3 H6 D2 D1 F4 D3 G6")),
        Subsignal("ba", Pins("F2 F1")),
        Subsignal("cke", Pins("H7")),
        Subsignal("ras_n", Pins("L5")),
        Subsignal("cas_n", Pins("K5")),
        Subsignal("we_n", Pins("E3")),
        Subsignal(
            "dq", Pins("L2 L1 K2 K1 H2 H1 J3 J1 M3 M1 N2 N1 T2 T1 U2 U1")
        ),
        Subsignal("dqs", Pins("L4 P2")),
        Subsignal("dm", Pins("K3 K4")),
        IOStandard("MOBILE_DDR")),

    # Small DIP switches
    # DP1 (user_sw:0) -> DP8 (user_sw:7)
    ("user_sw", 0, Pins("F17"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_sw", 1, Pins("F18"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_sw", 2, Pins("E16"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_sw", 3, Pins("E18"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_sw", 4, Pins("D18"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_sw", 5, Pins("D17"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_sw", 6, Pins("C18"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_sw", 7, Pins("C17"), IOStandard("LVCMOS33"), Misc("PULLUP")),

    # Despite being marked as "sw" these are actually buttons which need
    # debouncing.
    # sw1 (user_btn:0) through sw6 (user_btn:5)
    ("user_btn", 0, Pins("M18"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_btn", 1, Pins("L18"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_btn", 2, Pins("M16"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_btn", 3, Pins("L17"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    ("user_btn", 4, Pins("K17"), IOStandard("LVCMOS33"), Misc("PULLUP")),
    # Use SW6 as the reset button for now.
    ("user_btn", 5, Pins("K18"), IOStandard("LVCMOS33"), Misc("PULLUP")),

    # LEDs 1 through 8
    ("user_led", 0, Pins("P15"), IOStandard("LVCMOS33"), Drive(8)),
    ("user_led", 1, Pins("P16"), IOStandard("LVCMOS33"), Drive(8)),
    ("user_led", 2, Pins("N15"), IOStandard("LVCMOS33"), Drive(8)),
    ("user_led", 3, Pins("N16"), IOStandard("LVCMOS33"), Drive(8)),
    ("user_led", 4, Pins("U17"), IOStandard("LVCMOS33"), Drive(8)),
    ("user_led", 5, Pins("U18"), IOStandard("LVCMOS33"), Drive(8)),
    ("user_led", 6, Pins("T17"), IOStandard("LVCMOS33"), Drive(8)),
    ("user_led", 7, Pins("T18"), IOStandard("LVCMOS33"), Drive(8)),

    ("mmc", 0,
        Subsignal("data", Pins("K14 G18 J13 L13"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),

        Subsignal("cmd", Pins("G16"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),

        Subsignal("clk", Pins("L12"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST"))),

    ("sevenseg", 0,
        Subsignal("segment7", Pins("A3"), IOStandard("LVCMOS33")),  # A
        Subsignal("segment6", Pins("B4"), IOStandard("LVCMOS33")),  # B
        Subsignal("segment5", Pins("A4"), IOStandard("LVCMOS33")),  # C
        Subsignal("segment4", Pins("C4"), IOStandard("LVCMOS33")),  # D
        Subsignal("segment3", Pins("C5"), IOStandard("LVCMOS33")),  # E
        Subsignal("segment2", Pins("D6"), IOStandard("LVCMOS33")),  # F
        Subsignal("segment1", Pins("C6"), IOStandard("LVCMOS33")),  # G
        Subsignal("segment0", Pins("A5"), IOStandard("LVCMOS33")),  # Dot
        Subsignal("enable0", Pins("B2"), IOStandard("LVCMOS33")),   # EN0
        Subsignal("enable1", Pins("A2"), IOStandard("LVCMOS33")),   # EN1
        Subsignal("enable2", Pins("B3"), IOStandard("LVCMOS33"))),  # EN2


    ("audio", 0,
        Subsignal("channel1", Pins("B16"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),
        Subsignal("channel2", Pins("A16"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST"))),

    ("vga_out", 0,
        Subsignal("hsync_n", Pins("B12"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),
        Subsignal("vsync_n", Pins("A12"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),
        Subsignal("r", Pins("A9 B9 C9"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),
        Subsignal("g", Pins("C10 A10 C11"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),
        Subsignal("b", Pins("B11 A11"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")))
]

_connectors = [
    ("P6", "T3 R3 V5 U5 V4 T4 V7 U7"),
    ("P7", "V11 U11 V13 U13 T10 R10 T11 R11"),
    ("P8", "L16 L15 K16 K15 J18 J16 H18 H17")
]


class Platform(XilinxPlatform):
    name = "mimasv2"
    default_clk_name = "clk100"
    default_clk_period = 10

    def __init__(self):
        XilinxPlatform.__init__(self, "xc6slx9-csg324-2", _io, _connectors)

    def create_programmer(self):
        raise NotImplementedError
