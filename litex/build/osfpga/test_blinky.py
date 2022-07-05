#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.build.generic_platform import Pins
from litex.build.osfpga import OSFPGAPlatform

# Minimal Platform ---------------------------------------------------------------------------------

_io = [
    ("clk", 0, Pins(1)),
    ("led", 0, Pins(1))
]

class Platform(OSFPGAPlatform):
    def __init__(self):
        OSFPGAPlatform.__init__(self, device="gemini", toolchain="raptor", io=_io)

# Minimal Design -----------------------------------------------------------------------------------

platform = Platform()
clk      = platform.request("clk")
led      = platform.request("led")
module   = Module()
module.clock_domains.cd_sys = ClockDomain("sys")
module.comb += module.cd_sys.clk.eq(clk)
counter  = Signal(26)
module.comb += led.eq(counter[25])
module.sync += counter.eq(counter + 1)

# Build --------------------------------------------------------------------------------------------

platform.build(module, build_name="blinky", run=True)
