#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.boards.platforms import versa_ecp5

from litex.soc.cores.clock import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import AS4C32M16
from litedram.phy import GENSDRPHY


class _CRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain(reset_less=True)

        # # #

        # clk / rst
        clk100 = platform.request("clk100")
        rst_n = platform.request("rst_n")

        # pll
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~rst_n)
        pll.register_clkin(clk100, 100e6)
        pll.create_clkout(self.cd_sys, 50e6, phase=11)
        pll.create_clkout(self.cd_sys_ps, 50e6, phase=20)
        # FIXME: AsyncResetSynchronizer needs FD1S3BX support.
        #self.specials += AsyncResetSynchronizer(self.cd_sys, rst)
        self.comb += self.cd_sys.rst.eq(~rst_n)
        platform.add_period_constraint(self.cd_sys.clk, 20.0)
        platform.add_period_constraint(self.cd_sys_ps.clk, 20.0)

        # sdram clock
        self.comb += platform.request("sdram_clock").eq(self.cd_sys_ps.clk)


class BaseSoC(SoCSDRAM):
    def __init__(self, **kwargs):
        platform = versa_ecp5.Platform(toolchain="trellis")
        platform.add_extension(versa_ecp5._ecp5_soc_hat_io)
        sys_clk_freq = int(50e6)
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
                          integrated_rom_size=0x8000,
                          **kwargs)

        self.submodules.crg = _CRG(platform)

        if not self.integrated_main_ram_size:
            self.submodules.sdrphy = GENSDRPHY(platform.request("sdram"))
            sdram_module = AS4C32M16(sys_clk_freq, "1:1")
            self.register_sdram(self.sdrphy,
                                sdram_module.geom_settings,
                                sdram_module.timing_settings)

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC port to the Versa ECP5")
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()

if __name__ == "__main__":
    main()
