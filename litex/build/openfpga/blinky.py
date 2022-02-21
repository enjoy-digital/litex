#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.build.generic_platform import Pins
from litex.build.openfpga import OpenFPGAPlatform

# export LITEX_ENV_OPENFPGA=/home/florent/dev/openfpga/OpenFPGA
# export LITEX_ENV_OPENFPGA_SOFA=/home/florent/dev/openfpga/SOFA

# Minimal Platform ---------------------------------------------------------------------------------

_io = [
    ("clk", 0, Pins(1)),
    ("led", 0, Pins(1))
]

class Platform(OpenFPGAPlatform):
    def __init__(self):
        OpenFPGAPlatform.__init__(self, "FPGA1212_QLSOFA_HD", _io)

# Minimal Design -----------------------------------------------------------------------------------

platform = Platform()
clk      = platform.request("clk")
led      = platform.request("led")
module   = Module()
module.clock_domains.cd_sys = ClockDomain("sys")
module.cd_sys.clk.eq(clk)
counter  = Signal(26)
module.comb += led.eq(counter[25])
module.sync += counter.eq(counter + 1)

# Build --------------------------------------------------------------------------------------------

platform.build(module, run=True)
