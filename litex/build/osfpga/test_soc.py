#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.build.io import CRG
from litex.build.generic_platform import Pins, Subsignal
from litex.build.osfpga import OSFPGAPlatform

from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

# Platform ---------------------------------------------------------------------------------

_io = [
    # Clk.
    ("clk", 0, Pins(1)),

    # Serial.
    ("serial", 0,
        Subsignal("tx", Pins(1)),
        Subsignal("rx", Pins(1)),
    ),
]

class Platform(OSFPGAPlatform):
    def __init__(self, toolchain="raptor", device="gemini"):
        OSFPGAPlatform.__init__(self, device=device, toolchain=toolchain, io=_io)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, platform, sys_clk_freq=int(10e6), **kwargs):
        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(platform.request("clk"))

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, sys_clk_freq, ident="LiteX Test SoC on OS-FPGA", **kwargs)

# Build --------------------------------------------------------------------------------------------

def main():
    from litex.soc.integration.soc import LiteXSoCArgumentParser
    parser = LiteXSoCArgumentParser(description="LiteX Test SoC on OS-FPGA")
    target_group = parser.add_argument_group(title="Target options")
    target_group.add_argument("--build",     action="store_true", help="Build design.")
    target_group.add_argument("--toolchain", default="raptor",    help="FPGA toolchain.")
    target_group.add_argument("--device",    default="gemini",    help="FPGA device.")
    builder_args(parser)
    soc_core_args(parser)
    args = parser.parse_args()

    platform = Platform(toolchain=args.toolchain, device=args.device)
    soc      = BaseSoC(platform,**soc_core_argdict(args))
    builder  = Builder(soc, **builder_argdict(args))
    if args.build:
        builder.build()

if __name__ == "__main__":
    main()
