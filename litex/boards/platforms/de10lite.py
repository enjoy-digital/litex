# This file is Copyright (c) 2019 msloniewski <marcin.sloniewski@gmail.com>
# License: BSD

from litex.build.generic_platform import *
from litex.build.altera import AlteraPlatform
from litex.build.altera.programmer import USBBlaster


_io = [
    ("clk10", 0, Pins("N5"), IOStandard("3.3-V LVTTL")),
    ("clk50", 0, Pins("P11"), IOStandard("3.3-V LVTTL")),
    ("clk50", 1, Pins("N14"), IOStandard("3.3-V LVTTL")),

    ("serial", 0,
        Subsignal("tx", Pins("V10"), IOStandard("3.3-V LVTTL")), # JP1 GPIO[0]
        Subsignal("rx", Pins("W10"), IOStandard("3.3-V LVTTL"))  # JP1 GPIO[1]
    ),

    ("user_led", 0, Pins("A8"), IOStandard("3.3-V LVTTL")),
    ("user_led", 1, Pins("A9"), IOStandard("3.3-V LVTTL")),
    ("user_led", 2, Pins("A10"), IOStandard("3.3-V LVTTL")),
    ("user_led", 3, Pins("B10"), IOStandard("3.3-V LVTTL")),
    ("user_led", 4, Pins("D13"), IOStandard("3.3-V LVTTL")),
    ("user_led", 5, Pins("C13"), IOStandard("3.3-V LVTTL")),
    ("user_led", 6, Pins("E14"), IOStandard("3.3-V LVTTL")),
    ("user_led", 7, Pins("D14"), IOStandard("3.3-V LVTTL")),
    ("user_led", 8, Pins("A11"), IOStandard("3.3-V LVTTL")),
    ("user_led", 9, Pins("B11"), IOStandard("3.3-V LVTTL")),

    ("user_btn", 0, Pins("B8"), IOStandard("3.3-V LVTTL")),
    ("user_btn", 1, Pins("A7"), IOStandard("3.3-V LVTTL")),

    ("user_sw", 0, Pins("C10"), IOStandard("3.3-V LVTTL")),
    ("user_sw", 1, Pins("C11"), IOStandard("3.3-V LVTTL")),
    ("user_sw", 2, Pins("D12"), IOStandard("3.3-V LVTTL")),
    ("user_sw", 3, Pins("C12"), IOStandard("3.3-V LVTTL")),
    ("user_sw", 4, Pins("A12"), IOStandard("3.3-V LVTTL")),
    ("user_sw", 5, Pins("B12"), IOStandard("3.3-V LVTTL")),
    ("user_sw", 6, Pins("A13"), IOStandard("3.3-V LVTTL")),
    ("user_sw", 7, Pins("A14"), IOStandard("3.3-V LVTTL")),
    ("user_sw", 8, Pins("B14"), IOStandard("3.3-V LVTTL")),
    ("user_sw", 9, Pins("F15"), IOStandard("3.3-V LVTTL")),

    # 7-segment displays
    ("seven_seg", 0, Pins("C14 E15 C15 C16 E16 D17 C17 D15"), IOStandard("3.3-V LVTTL")),
    ("seven_seg", 1, Pins("C18 D18 E18 B16 A17 A18 B17 A16"), IOStandard("3.3-V LVTTL")),
    ("seven_seg", 2, Pins("B20 A20 B19 A21 B21 C22 B22 A19"), IOStandard("3.3-V LVTTL")),
    ("seven_seg", 3, Pins("F21 E22 E21 C19 C20 D19 E17 D22"), IOStandard("3.3-V LVTTL")),
    ("seven_seg", 4, Pins("F18 E20 E19 J18 H19 F19 F20 F17"), IOStandard("3.3-V LVTTL")),
    ("seven_seg", 5, Pins("J20 K20 L18 N18 M20 N19 N20 L19"), IOStandard("3.3-V LVTTL")),


    ("gpio_0", 0,
        Pins("V10 W10 V9 W9 V8 W8 V7 W7 W6 V5 W5 AA15 AA14 W13 W12 AB13 AB12 Y11 AB11 W11 AB10 AA10 AA9 Y8 AA8 Y7 AA7 Y6 AA6 Y5 AA5 Y4 AB3 Y3 AB2 AA2"),
        IOStandard("3.3-V LVTTL")
    ),
    ("gpio_1", 0,
        Pins("AB5 AB6 AB7 AB8 AB9 Y10 AA11 AA12 AB17 AA17 AB19 AA19 Y19 AB20 AB21 AA20 F16"),
        IOStandard("3.3-V LVTTL")
    ),

    ("vga_out", 0,
        Subsignal("hsync_n", Pins("N3")),
        Subsignal("vsync_n", Pins("N1")),
        Subsignal("r", Pins("AA1 V1 Y2 Y1")),
        Subsignal("g", Pins("W1 T2 R2 R1")),
        Subsignal("b", Pins("P1 T1 P4 N2")),
        IOStandard("3.3-V LVTTL")
    ),

    ("sdram_clock", 0, Pins("L14"), IOStandard("3.3-V LVTTL")),
    ("sdram", 0,
        Subsignal("a", Pins("U17 W19 V18 U18 U19 T18 T19 R18 P18 P19 T20 P20 R20")),
        Subsignal("ba", Pins("T21 T22")),
        Subsignal("cs_n", Pins("U20")),
        Subsignal("cke", Pins("N22")),
        Subsignal("ras_n", Pins("U22")),
        Subsignal("cas_n", Pins("U21")),
        Subsignal("we_n", Pins("V20")),
        Subsignal("dq", Pins("Y21 Y20 AA22 AA21 Y22 W22 W20 V21 P21 J22 H21 H22 G22 G20 G19 F22")),
        Subsignal("dm", Pins("V22 J21")),
        IOStandard("3.3-V LVTTL")
    ),

    ("accelerometer", 0,
        Subsignal("int1", Pins("Y14")),
        Subsignal("int1", Pins("Y13")),
        Subsignal("mosi", Pins("V11")),
        Subsignal("miso", Pins("V12")),
        Subsignal("clk", Pins("AB15")),
        Subsignal("cs_n", Pins("AB16")),
        IOStandard("3.3-V LVTTL")
    )
]


class Platform(AlteraPlatform):
    default_clk_name = "clk50"
    default_clk_period = 20
    create_rbf = False

    def __init__(self):
        AlteraPlatform.__init__(self, "10M50DAF484C7G", _io)

    def create_programmer(self):
        return USBBlaster()
