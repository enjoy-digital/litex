#!/usr/bin/env python3

import argparse
import importlib

from migen import *
from migen.genlib.io import CRG

from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

from liteeth.phy import LiteEthPHY
from liteeth.core.mac import LiteEthMAC

class BaseSoC(SoCCore):
    def __init__(self, platform, **kwargs):
        sys_clk_freq = int(1e9/platform.default_clk_period)
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq,
            integrated_rom_size=0x8000,
            integrated_main_ram_size=16*1024,
            **kwargs)
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))


class EthernetSoC(BaseSoC):
    csr_map = {
        "ethphy": 20,
        "ethmac": 21
    }
    csr_map.update(BaseSoC.csr_map)

    interrupt_map = {
        "ethmac": 3,
    }
    interrupt_map.update(BaseSoC.interrupt_map)

    mem_map = {
        "ethmac": 0x30000000,  # (shadow @0xb0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, platform, **kwargs):
        BaseSoC.__init__(self, platform, **kwargs)

        self.submodules.ethphy = LiteEthPHY(platform.request("eth_clocks"),
                                            platform.request("eth"))
        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
            interface="wishbone", endianness=self.cpu.endianness, with_preamble_crc=False)
        self.add_wb_slave(mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus)
        self.add_memory_region("ethmac", self.mem_map["ethmac"] | self.shadow_base, 0x2000)


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
