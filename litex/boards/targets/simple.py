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
from liteeth.mac import LiteEthMAC

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, platform, integrated_rom_size=0x8000, **kwargs):
        sys_clk_freq = int(1e9/platform.default_clk_period)

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq,
            integrated_rom_size=integrated_rom_size,
            integrated_main_ram_size=16*1024,
            **kwargs)
        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

# EthernetSoC --------------------------------------------------------------------------------------

class EthernetSoC(BaseSoC):
    mem_map = {
        "ethmac": 0xb0000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, platform, integrated_rom_size=0x10000, **kwargs):
        BaseSoC.__init__(self, platform, **kwargs)

        self.submodules.ethphy = LiteEthPHY(platform.request("eth_clocks"),
                                            platform.request("eth"))
        self.add_csr("ethphy")
        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
            interface="wishbone", endianness=self.cpu.endianness, with_preamble_crc=False)
        self.add_wb_slave(self.mem_map["ethmac"], self.ethmac.bus, 0x2000)
        self.add_memory_region("ethmac", self.mem_map["ethmac"], 0x2000, type="io")
        self.add_csr("ethmac")
        self.add_interrupt("ethmac")

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
    cls = EthernetSoC if args.with_ethernet else BaseSoC
    soc = cls(platform, **soc_core_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
