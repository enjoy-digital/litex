#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.boards.platforms import ulx3s

from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import MT48LC16M16
from litedram.phy import GENSDRPHY


class _CRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain()

        # # #

        clk25 = platform.request("clk25")
        rst = platform.request("rst")

        # sys_clk
        self.comb += self.cd_sys.clk.eq(clk25)
        # FIXME: AsyncResetSynchronizer needs FD1S3BX support.
        #self.specials += AsyncResetSynchronizer(self.cd_sys, rst)
        self.comb += self.cd_sys.rst.eq(rst)

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

        # Stop ESP32 from resetting FPGA
        wifi_gpio0 = platform.request("wifi_gpio0")
        self.comb += wifi_gpio0.eq(1)


class BaseSoC(SoCSDRAM):
    def __init__(self, **kwargs):
        platform = ulx3s.Platform(toolchain="prjtrellis")
        sys_clk_freq = int(25e6)
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
                          l2_size=32,
                          integrated_rom_size=0x8000,
                          **kwargs)

        self.submodules.crg = _CRG(platform)

        if not self.integrated_main_ram_size:
            self.submodules.sdrphy = GENSDRPHY(platform.request("sdram"))
            sdram_module = MT48LC16M16(sys_clk_freq, "1:1")
            self.register_sdram(self.sdrphy,
                                sdram_module.geom_settings,
                                sdram_module.timing_settings)


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
