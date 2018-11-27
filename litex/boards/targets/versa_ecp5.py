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
from litedram.core.controller import ControllerSettings


class _CRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain()

        # # #

        # clk / rst
        clk100 = platform.request("clk100")
        rst_n = platform.request("rst_n")
        platform.add_period_constraint(clk100, 10.0)

        # pll
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~rst_n)
        pll.register_clkin(clk100, 100e6)
        pll.create_clkout(self.cd_sys, 50e6)
        # FIXME: AsyncResetSynchronizer needs FD1S3BX support.
        #self.specials += AsyncResetSynchronizer(self.cd_sys, rst)
        self.comb += self.cd_sys.rst.eq(~rst_n)

        # sys_clk phase shifted (for sdram)
        sdram_ps_clk = self.cd_sys.clk
        # FIXME: phase shift with luts, needs PLL support.
        sdram_ps_luts = 5
        for i in range(sdram_ps_luts):
            new_sdram_ps_clk = Signal()
            self.specials += Instance("LUT4",
                p_INIT=2,
                i_A=sdram_ps_clk,
                i_B=0,
                i_C=0,
                i_D=0,
                o_Z=new_sdram_ps_clk)
            sdram_ps_clk = new_sdram_ps_clk
        self.comb += self.cd_sys_ps.clk.eq(sdram_ps_clk)
        sdram_clock = platform.request("sdram_clock")
        self.comb += sdram_clock.eq(sdram_ps_clk)


class BaseSoC(SoCSDRAM):
    def __init__(self, **kwargs):
        platform = versa_ecp5.Platform(toolchain="trellis")
        platform.add_extension(versa_ecp5._ecp5_soc_hat_io)
        sys_clk_freq = int(50e6)
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
                          l2_size=32,
                          integrated_rom_size=0x8000,
                          **kwargs)

        self.submodules.crg = _CRG(platform)

        if not self.integrated_main_ram_size:
            self.submodules.sdrphy = GENSDRPHY(platform.request("sdram"))
            sdram_module = AS4C32M16(sys_clk_freq, "1:1")
            self.register_sdram(self.sdrphy,
                                sdram_module.geom_settings,
                                sdram_module.timing_settings,
                                controller_settings=ControllerSettings(
                                    with_refresh=False)) # FIXME


def main():
    parser = argparse.ArgumentParser(description="LiteX SoC port to the ULX3S")
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
