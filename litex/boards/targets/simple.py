#!/usr/bin/env python3

# This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# License: BSD

import argparse
import importlib

from migen import *
from migen.genlib.io import CRG

from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

from liteeth.phy import LiteEthPHY

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, platform, with_ethernet=False, **kwargs):
        sys_clk_freq = int(1e9/platform.default_clk_period)

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq, **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        # Ethernet ---------------------------------------------------------------------------------
        if with_ethernet:
            self.submodules.ethphy = LiteEthPHY(
                clock_pads = self.platform.request("eth_clocks"),
                pads       = self.platform.request("eth"),
                clk_freq   = self.clk_freq)
            self.add_csr("ethphy")
            self.add_ethernet(phy=self.ethphy)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generic LiteX SoC")
    builder_args(parser)
    soc_core_args(parser)
    parser.add_argument("--with-ethernet", action="store_true",
                        help="enable Ethernet support")
    parser.add_argument("platform",
                        help="module name of the platform to build for")
    parser.add_argument("--gateware-toolchain", default=None,
                        help="FPGA gateware toolchain used for build")
    args = parser.parse_args()

    platform_module = importlib.import_module(args.platform)
    if args.gateware_toolchain is not None:
        platform = platform_module.Platform(toolchain=args.gateware_toolchain)
    else:
        platform = platform_module.Platform()
    soc = BaseSoC(platform, with_ethernet=args.with_ethernet, **soc_core_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
