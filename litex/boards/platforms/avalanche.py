#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build.microsemi import MicrosemiPlatform

# IOs ----------------------------------------------------------------------------------------------

_io = [
    # Clk / Rst
    ("clk50", 0, Pins("R1"), IOStandard("LVCMOS25")),
    ("clk50", 1, Pins("J3"), IOStandard("LVCMOS25")),
    ("rst_n", 0, Pins("F5"), IOStandard("LVCMOS33")),

    # Leds
    ("user_led", 0, Pins("D6"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("D7"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("D8"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("D9"), IOStandard("LVCMOS33")),

    # Buttons
    ("user_btn", 0, Pins("E13"), IOStandard("LVCMOS33")),
    ("user_btn", 1, Pins("E14"), IOStandard("LVCMOS33")),

    # Serial
    ("serial", 0,
        Subsignal("tx", Pins("F17")),
        Subsignal("rx", Pins("F16")),
        IOStandard("LVCMOS33")
    ),

    # SPIFlash
    ("spiflash", 0,
        Subsignal("clk",  Pins("J1")),
        Subsignal("cs_n", Pins("H1")),
        Subsignal("mosi", Pins("F2")),
        Subsignal("miso", Pins("F1")),
        Subsignal("wp",   Pins("M7")),
        Subsignal("hold", Pins("M8")),
        IOStandard("LVCMOS25"),
    ),
    ("spiflash4x", 0,
        Subsignal("clk",  Pins("J1")),
        Subsignal("cs_n", Pins("H1")),
        Subsignal("dq",   Pins("F2 F1 M7 M8")),
        IOStandard("LVCMOS25")
    ),

    # DDR3 SDRAM
    ("ddram", 0,
        Subsignal("a", Pins(
            "U5 U4  V4  W3 V5 W4  Y3 AA3",
            "Y4 Y5 AA2 AB2 V6 W6 AB3"),
            IOStandard("SSTL15II")),
        Subsignal("ba",    Pins("V7 Y6 U7"), IOStandard("SSTL15II")),
        Subsignal("ras_n", Pins("AA6"), IOStandard("SSTL15II")),
        Subsignal("cas_n", Pins("AA5"), IOStandard("SSTL15II")),
        Subsignal("we_n",  Pins("AB5"), IOStandard("SSTL15II")),
        Subsignal("cs_n",  Pins("W7"),  IOStandard("SSTL15II")),
        Subsignal("dm", Pins("Y9 R15"), IOStandard("SSTL15II")),
        Subsignal("dq", Pins(
            "T7   T8  U8 U9  R10  V9 V10 W9",
            "V14 U14 R12 T11 U15 T13 U13 T15"),
            IOStandard("SSTL15II")),
        Subsignal("dqs_p", Pins("T10 R13"), IOStandard("SSTL15II")),
        Subsignal("dqs_n", Pins("U10 T12"), IOStandard("SSTL15II")),
        Subsignal("clk_p", Pins("V2"), IOStandard("SSTL15II")),
        Subsignal("clk_n", Pins("W2"), IOStandard("SSTL15II")),
        Subsignal("cke", Pins("W8"),  IOStandard("SSTL15II")),
        Subsignal("odt", Pins("AA7"), IOStandard("SSTL15II")),
        Subsignal("reset_n", Pins("AB7"), IOStandard("SSTL15II")),
    ),

    # Ethernet
    ("eth_clocks", 0,
        Subsignal("tx", Pins("J8")),
        Subsignal("rx", Pins("K3")),
        IOStandard("LVCMOS25")
    ),
    ("eth", 0,
        Subsignal("rst_n",   Pins("L8"), IOStandard("LVCMOS33")),
        Subsignal("int_n",   Pins("J4")),
        Subsignal("mdio",    Pins("H2")),
        Subsignal("mdc",     Pins("J2")),
        Subsignal("rx_ctl",  Pins("K5")),
        Subsignal("rx_data", Pins("J9 K1 K6 K4")),
        Subsignal("tx_ctl",  Pins("L5")),
        Subsignal("tx_data", Pins("K8 L1 L2 L3")),
        IOStandard("LVCMOS25")
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(MicrosemiPlatform):
    default_clk_name   = "clk50"
    default_clk_period = 1e9/50e6

    def __init__(self):
        MicrosemiPlatform.__init__(self, "MPF300TS_ES-FCG484-1", _io)

    def do_finalize(self, fragment):
        MicrosemiPlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk50", 0, loose=True), 1e9/50e6)
        self.add_period_constraint(self.lookup_request("clk50", 1, loose=True), 1e9/50e6)
