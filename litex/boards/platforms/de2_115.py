# SPDX-License-Identifier: BSD-2-Clause
#
# Copyright (c) 2019 Antony Pavlov <antonynpavlov@gmail.com>

from litex.build.generic_platform import *
from litex.build.altera import AlteraPlatform

# IOs ------------------------------------------------------------------

_io = [
    ("clk50", 0, Pins("Y2"), IOStandard("3.3-V LVTTL")),

    ("serial", 0,
        Subsignal("tx", Pins("AB22"), IOStandard("3.3-V LVTTL")), # JP5 GPIO[0]
        Subsignal("rx", Pins("AC15"), IOStandard("3.3-V LVTTL"))  # JP5 GPIO[1]
    ),

    ("sdram_clock", 0, Pins("AE5"), IOStandard("3.3-V LVTTL")),
    ("sdram", 0,
        Subsignal("a", Pins("R6 V8 U8 P1 V5 W8 W7 AA7 Y5 Y6 R5 AA5 Y7")),
        Subsignal("ba", Pins("U7 R4")),
        Subsignal("cs_n", Pins("T4")),
        Subsignal("cke", Pins("AA6")),
        Subsignal("ras_n", Pins("U6")),
        Subsignal("cas_n", Pins("V7")),
        Subsignal("we_n", Pins("V6")),
        Subsignal("dq", Pins("W3 W2 V4 W1 V3 V2 V1 U3 Y3 Y4 AB1 AA3 AB2 AC1 AB3 AC2")),
        Subsignal("dm", Pins("U2 W4")),
        IOStandard("3.3-V LVTTL")
    ),
]

# Platform -------------------------------------------------------------

class Platform(AlteraPlatform):
    default_clk_name = "clk50"
    default_clk_period = 20

    def __init__(self):
        AlteraPlatform.__init__(self, "EP4CE115F29C7", _io)
