# SPDX-License-Identifier: BSD-2-Clause
#
# Copyright (c) 2019 Antony Pavlov <antonynpavlov@gmail.com>

from litex.build.generic_platform import *
from litex.build.altera import AlteraPlatform

# IOs ------------------------------------------------------------------

_io = [
    ("clk50", 0, Pins("AF14"), IOStandard("3.3-V LVTTL")),

    ("serial", 0,
        Subsignal("tx", Pins("AC18"), IOStandard("3.3-V LVTTL")), # JP1 GPIO[0]
        Subsignal("rx", Pins("Y17"), IOStandard("3.3-V LVTTL"))   # JP1 GPIO[1]
    ),

    ("sdram_clock", 0, Pins("AH12"), IOStandard("3.3-V LVTTL")),
    ("sdram", 0,
        Subsignal("a", Pins("AK14 AH14 AG15 AE14 AB15 AC14 AD14 AF15 AH15 AG13 AG12 AH13 AJ14")),
        Subsignal("ba", Pins("AF13 AJ12")),
        Subsignal("cs_n", Pins("AG11")),
        Subsignal("cke", Pins("AK13")),
        Subsignal("ras_n", Pins("AE13")),
        Subsignal("cas_n", Pins("AF11")),
        Subsignal("we_n", Pins("AA13")),
        Subsignal("dq", Pins("AK6 AJ7 AK7 AK8 AK9 AG10 AK11 AJ11 AH10 AJ10 AJ9 AH9 AH8 AH7 AJ6 AJ5")),
        Subsignal("dm", Pins("AB13 AK12")),
        IOStandard("3.3-V LVTTL")
    ),
]

# Platform -------------------------------------------------------------

class Platform(AlteraPlatform):
    default_clk_name = "clk50"
    default_clk_period = 20

    def __init__(self):
        AlteraPlatform.__init__(self, "5CSEMA5F31C6", _io)
