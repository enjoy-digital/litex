#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.lattice.programmer import UJProg

# IOs ----------------------------------------------------------------------------------------------

_io_common = [
    ("clk25", 0, Pins("G2"), IOStandard("LVCMOS33")),
    ("rst",   0, Pins("R1"), IOStandard("LVCMOS33")),

    ("user_led", 0, Pins("B2"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("C2"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("C1"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("D2"), IOStandard("LVCMOS33")),
    ("user_led", 4, Pins("D1"), IOStandard("LVCMOS33")),
    ("user_led", 5, Pins("E2"), IOStandard("LVCMOS33")),
    ("user_led", 6, Pins("E1"), IOStandard("LVCMOS33")),
    ("user_led", 7, Pins("H3"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("tx", Pins("L4"), IOStandard("LVCMOS33")),
        Subsignal("rx", Pins("M1"), IOStandard("LVCMOS33"))
    ),

    ("sdram_clock", 0, Pins("F19"), IOStandard("LVCMOS33")),
    ("sdram", 0,
        Subsignal("a",     Pins(
            "M20 M19 L20 L19 K20 K19 K18 J20",
            "J19 H20 N19 G20 G19")),
        Subsignal("dq",    Pins(
            "J16 L18 M18 N18 P18 T18 T17 U20",
            "E19 D20 D19 C20 E18 F18 J18 J17")),
        Subsignal("we_n",  Pins("T20")),
        Subsignal("ras_n", Pins("R20")),
        Subsignal("cas_n", Pins("T19")),
        Subsignal("cs_n",  Pins("P20")),
        Subsignal("cke",   Pins("F20")),
        Subsignal("ba",    Pins("P19 N20")),
        Subsignal("dm",    Pins("U19 E20")),
        IOStandard("LVCMOS33"),
        Misc("SLEWRATE=FAST"),
    ),

    ("wifi_gpio0", 0, Pins("L2"), IOStandard("LVCMOS33")),

    ("ext0p", 0, Pins("B11"), IOStandard("LVCMOS33")),
    ("ext1p", 0, Pins("A10"), IOStandard("LVCMOS33")),

    ("gpio", 0,
        Subsignal("p", Pins("B11")),
        Subsignal("n", Pins("C11")),
        IOStandard("LVCMOS33")
    ),
    ("gpio", 1,
        Subsignal("p", Pins("A10")),
        Subsignal("n", Pins("A11")),
        IOStandard("LVCMOS33")
    ),
    ("gpio", 2,
        Subsignal("p", Pins("A9")),
        Subsignal("n", Pins("B10")),
        IOStandard("LVCMOS33")
    ),
    ("gpio", 3,
        Subsignal("p", Pins("B9")),
        Subsignal("n", Pins("C10")),
        IOStandard("LVCMOS33")
    ),

    ("usb", 0,
        Subsignal("d_p", Pins("D15")),
        Subsignal("d_n", Pins("E15")),
        Subsignal("pullup", Pins("B12 C12")),
        IOStandard("LVCMOS33")
    ),
    ("oled_spi", 0,
        Subsignal("clk",  Pins("P4")),
        Subsignal("mosi", Pins("P3")),
        IOStandard("LVCMOS33"),
    ),
    ("oled_ctl", 0,
        Subsignal("dc",   Pins("P1")),
        Subsignal("resn", Pins("P2")),
        Subsignal("csn",  Pins("N2")),
        IOStandard("LVCMOS33"),
    ),
]

_io_1_7 = [
    ("spisdcard", 0,
        Subsignal("clk",  Pins("J1")),
        Subsignal("mosi", Pins("J3"), Misc("PULLMODE=UP")),
        Subsignal("cs_n", Pins("H1"), Misc("PULLMODE=UP")),
        Subsignal("miso", Pins("K2"), Misc("PULLMODE=UP")),
        Misc("SLEWRATE=FAST"),
        IOStandard("LVCMOS33"),
    ),

    ("sdcard", 0,
        Subsignal("clk",  Pins("J1")),
        Subsignal("cmd",  Pins("J3"), Misc("PULLMODE=UP")),
        Subsignal("data", Pins("K2 K1 H2 H1"), Misc("PULLMODE=UP")),
        Misc("SLEWRATE=FAST"),
        IOStandard("LVCMOS33"),
    ),
]

_io_2_0 = [
    ("spisdcard", 0,
        Subsignal("clk",  Pins("H2")),
        Subsignal("mosi", Pins("J1"), Misc("PULLMODE=UP")),
        Subsignal("cs_n", Pins("K2"), Misc("PULLMODE=UP")),
        Subsignal("miso", Pins("J3"), Misc("PULLMODE=UP")),
        Misc("SLEWRATE=FAST"),
        IOStandard("LVCMOS33"),
    ),

    ("sdcard", 0,
        Subsignal("clk",  Pins("H2")),
        Subsignal("cmd",  Pins("J1"), Misc("PULLMODE=UP")),
        Subsignal("data", Pins("J3 H1 K1 K2"), Misc("PULLMODE=UP")),
        Subsignal("cd", Pins("N5")),
        Subsignal("wp", Pins("P5")),
        Misc("SLEWRATE=FAST"),
        IOStandard("LVCMOS33"),
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(LatticePlatform):
    default_clk_name   = "clk25"
    default_clk_period = 1e9/25e6

    def __init__(self, device="LFE5U-45F", revision="2.0", **kwargs):
        assert device in ["LFE5U-25F", "LFE5U-45F", "LFE5U-85F"]
        assert revision in ["1.7", "2.0"]
        _io = _io_common + {"1.7": _io_1_7, "2.0": _io_2_0}[revision]
        LatticePlatform.__init__(self, device + "-6BG381C", _io, **kwargs)

    def create_programmer(self):
        return UJProg()

    def do_finalize(self, fragment):
        LatticePlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk25", loose=True), 1e9/25e6)
