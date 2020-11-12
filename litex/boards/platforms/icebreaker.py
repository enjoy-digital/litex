#
# This file is part of LiteX.
#
# Copyright (c) 2020 Piotr Esden-Tempski <piotr@esden.net>
# SPDX-License-Identifier: BSD-2-Clause

# iCEBreaker FPGA:
# - Crowd Supply campaign: https://www.crowdsupply.com/1bitsquared/icebreaker
# - 1BitSquared Store: https://1bitsquared.com/products/icebreaker
# - Design files: https://github.com/icebreaker/icebreaker

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.lattice.programmer import IceStormProgrammer

# IOs ----------------------------------------------------------------------------------------------

_io = [
    # Clk / Rst
    ("clk12", 0, Pins("35"), IOStandard("LVCMOS33")),

    # Leds
    ("user_led_n",    0, Pins("11"), IOStandard("LVCMOS33")),
    ("user_led_n",    1, Pins("37"), IOStandard("LVCMOS33")),

    ("user_ledr_n",   0, Pins("11"), IOStandard("LVCMOS33")), # Color-specific alias
    ("user_ledg_n",   0, Pins("37"), IOStandard("LVCMOS33")), # Color-specific alias

    # Button
    ("user_btn_n",    0, Pins("10"), IOStandard("LVCMOS33")),

    # Serial
    ("serial", 0,
        Subsignal("rx", Pins("6")),
        Subsignal("tx", Pins("9"), Misc("PULLUP")),
        IOStandard("LVCMOS33")
    ),

    # SPIFlash
    ("spiflash", 0,
        Subsignal("cs_n", Pins("16"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("15"), IOStandard("LVCMOS33")),
        Subsignal("miso", Pins("17"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("14"), IOStandard("LVCMOS33")),
        Subsignal("wp",   Pins("12"), IOStandard("LVCMOS33")),
        Subsignal("hold", Pins("13"), IOStandard("LVCMOS33")),
    ),
    ("spiflash4x", 0,
        Subsignal("cs_n", Pins("16"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("15"), IOStandard("LVCMOS33")),
        Subsignal("dq",   Pins("14 17 12 13"), IOStandard("LVCMOS33")),
    ),
]

# Connectors ---------------------------------------------------------------------------------------

_connectors = [
    ("PMOD1A", "4   2 47 45  3 48 46 44"),
    ("PMOD1B", "43 38 34 31 42 36 32 28"),
    ("PMOD2",  "27 25 21 19 26 23 20 18")
]

# The attached LED/button section can be either used standalone or as a PMOD.
# Attach to platform using:
# plat.add_extension(break_off_pmod)
# pmod_btn = plat.request("user_btn")
break_off_pmod = [
     ("user_btn", 0, Pins("PMOD2:6"), IOStandard("LVCMOS33")),
     ("user_btn", 1, Pins("PMOD2:3"), IOStandard("LVCMOS33")),
     ("user_btn", 2, Pins("PMOD2:7"), IOStandard("LVCMOS33")),

     ("user_led", 0, Pins("PMOD2:4"), IOStandard("LVCMOS33")),
     ("user_led", 1, Pins("PMOD2:0"), IOStandard("LVCMOS33")),
     ("user_led", 2, Pins("PMOD2:1"), IOStandard("LVCMOS33")),
     ("user_led", 3, Pins("PMOD2:5"), IOStandard("LVCMOS33")),
     ("user_led", 4, Pins("PMOD2:2"), IOStandard("LVCMOS33")),

     # Color-specific aliases
     ("user_ledr", 0, Pins("PMOD2:4"), IOStandard("LVCMOS33")),
     ("user_ledg", 0, Pins("PMOD2:0"), IOStandard("LVCMOS33")),
     ("user_ledg", 1, Pins("PMOD2:1"), IOStandard("LVCMOS33")),
     ("user_ledg", 2, Pins("PMOD2:5"), IOStandard("LVCMOS33")),
     ("user_ledg", 3, Pins("PMOD2:2"), IOStandard("LVCMOS33"))
]

# Platform -----------------------------------------------------------------------------------------

class Platform(LatticePlatform):
    default_clk_name   = "clk12"
    default_clk_period = 1e9/12e6

    def __init__(self, toolchain="icestorm"):
        LatticePlatform.__init__(self, "ice40-up5k-sg48", _io, _connectors, toolchain=toolchain)

    def create_programmer(self):
        return IceStormProgrammer()

    def do_finalize(self, fragment):
        LatticePlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk12", loose=True), 1e9/12e6)
