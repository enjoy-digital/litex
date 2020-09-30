#
# This file is part of LiteX.
#
# Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build.altera import AlteraPlatform
from litex.build.altera.programmer import USBBlaster

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("clk50", 0, Pins("R8"), IOStandard("3.3-V LVTTL")),

    ("user_led", 0, Pins("A15"), IOStandard("3.3-V LVTTL")),
    ("user_led", 1, Pins("A13"), IOStandard("3.3-V LVTTL")),
    ("user_led", 2, Pins("B13"), IOStandard("3.3-V LVTTL")),
    ("user_led", 3, Pins("A11"), IOStandard("3.3-V LVTTL")),
    ("user_led", 4, Pins("D1"),  IOStandard("3.3-V LVTTL")),
    ("user_led", 5, Pins("F3"),  IOStandard("3.3-V LVTTL")),
    ("user_led", 6, Pins("B1"),  IOStandard("3.3-V LVTTL")),
    ("user_led", 7, Pins("L3"),  IOStandard("3.3-V LVTTL")),

    ("key", 0, Pins("J15"), IOStandard("3.3-V LVTTL")),
    ("key", 1, Pins("E1"),  IOStandard("3.3-V LVTTL")),

    ("sw", 0, Pins("M1"),  IOStandard("3.3-V LVTTL")),
    ("sw", 1, Pins("T8"),  IOStandard("3.3-V LVTTL")),
    ("sw", 2, Pins("B9"),  IOStandard("3.3-V LVTTL")),
    ("sw", 3, Pins("M15"), IOStandard("3.3-V LVTTL")),

    ("serial", 0,
        # Compatible with cheap FT232 based cables (ex: Gaoominy 6Pin Ftdi Ft232Rl Ft232)
        # GND on JP1 Pin 12.
        Subsignal("tx", Pins("B5"), IOStandard("3.3-V LVTTL")), # GPIO_07 (JP1 Pin 10)
        Subsignal("rx", Pins("B4"), IOStandard("3.3-V LVTTL"))  # GPIO_05 (JP1 Pin 8)
    ),

    ("sdram_clock", 0, Pins("R4"), IOStandard("3.3-V LVTTL")),
    ("sdram", 0,
        Subsignal("a",     Pins(
            "P2 N5 N6 M8 P8 T7 N8 T6",
            "R1 P1 N2 N1 L4")),
        Subsignal("ba",    Pins("M7 M6")),
        Subsignal("cs_n",  Pins("P6")),
        Subsignal("cke",   Pins("L7")),
        Subsignal("ras_n", Pins("L2")),
        Subsignal("cas_n", Pins("L1")),
        Subsignal("we_n",  Pins("C2")),
        Subsignal("dq", Pins(
            "G2 G1 L8 K5 K2 J2 J1 R7",
            "T4 T2 T3 R3 R5 P3 N3 K1")),
        Subsignal("dm", Pins("R6 T5")),
        IOStandard("3.3-V LVTTL")
    ),

    ("epcs", 0,
        Subsignal("data0", Pins("H2")),
        Subsignal("dclk",  Pins("H1")),
        Subsignal("ncs0",  Pins("D2")),
        Subsignal("asd0",  Pins("C1")),
        IOStandard("3.3-V LVTTL")
    ),

    ("i2c", 0,
        Subsignal("sclk", Pins("F2")),
        Subsignal("sdat", Pins("F1")),
        IOStandard("3.3-V LVTTL")
    ),

    ("g_sensor", 0,
        Subsignal("cs_n", Pins("G5")),
        Subsignal("int",  Pins("M2")),
        IOStandard("3.3-V LVTTL")
    ),

    ("adc", 0,
        Subsignal("cs_n",  Pins("A10")),
        Subsignal("saddr", Pins("B10")),
        Subsignal("sclk",  Pins("B14")),
        Subsignal("sdat",  Pins("A9")),
        IOStandard("3.3-V LVTTL")
    ),

    ("gpio_0", 0, Pins(
        "D3 C3  A2  A3  B3  B4  A4  B5",
        "A5 D5  B6  A6  B7  D6  A7  C6",
        "C8 E6  E7  D8  E8  F8  F9  E9",
        "C9 D9 E11 E10 C11 B11 A12 D11",
        "D12 B12"),
        IOStandard("3.3-V LVTTL")
    ),
    ("gpio_1", 0, Pins(
        "F13 T15 T14 T13 R13 T12 R12 T11",
        "T10 R11 P11 R10 N12  P9  N9 N11",
        "L16 K16 R16 L15 P15 P16 R14 N16",
        "N15 P14 L14 N14 M10 L13 J16 K15",
        "J13 J14"),
        IOStandard("3.3-V LVTTL")
    ),
    ("gpio_2", 0, Pins(
        "A14 B16 C14 C16 C15 D16 D15 D14",
        "F15 F16 F14 G16 G15"),
        IOStandard("3.3-V LVTTL")
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(AlteraPlatform):
    default_clk_name   = "clk50"
    default_clk_period = 1e9/50e6

    def __init__(self):
        AlteraPlatform.__init__(self, "EP4CE22F17C6", _io)

    def create_programmer(self):
        return USBBlaster()

    def do_finalize(self, fragment):
        AlteraPlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk50", loose=True), 1e9/50e6)
