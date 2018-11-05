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
        # FIXME: AsyncResetSynchronizer needs FD1S3BX support.
        #self.specials += AsyncResetSynchronizer(self.cd_sys, rst)
        self.comb += self.cd_sys.rst.eq(rst)
        self.comb += self.cd_sys_ps.rst.eq(rst)

        sys_clk = Signal()
        sdram_ps_clk = Signal()

        self.specials += Instance(
            "EHXPLLL",
            i_CLKI=clk25,
            i_CLKFB=sys_clk,
            i_PHASESEL1=0,
            i_PHASESEL0=0,
            i_PHASEDIR=0,
            i_PHASESTEP=0,
            i_PHASELOADREG=0,
            i_STDBY=0,
            i_PLLWAKESYNC=0,
            i_RST=0,
            i_ENCLKOP=0,
            i_ENCLKOS=0,
            o_CLKOP=sys_clk,
            o_CLKOS=sdram_ps_clk,
            p_CLKOS_FPHASE=2,
            p_CLKOS_CPHASE=15,
            p_CLKOP_FPHASE=0,
            p_CLKOP_CPHASE=12,
            p_PLL_LOCK_MODE=0,
            p_OUTDIVIDER_MUXB="DIVB",
            p_CLKOS_ENABLE="ENABLED",
            p_CLKOP_ENABLE="ENABLED",
            p_CLKOS_DIV=13,
            p_CLKOP_DIV=13,
            p_CLKFB_DIV=2,
            p_CLKI_DIV=1,
            p_FEEDBK_PATH="CLKOP",
            attr=[("ICP_CURRENT", "6"), ("LPF_RESISTOR", "16"), ("MFG_ENABLE_FILTEROPAMP", "1"), ("MFG_GMCREF_SEL", "2")]
        )

        self.comb += self.cd_sys.clk.eq(sys_clk)
        self.comb += self.cd_sys_ps.clk.eq(sdram_ps_clk)
        sdram_clock = platform.request("sdram_clock")
        self.comb += sdram_clock.eq(sys_clk)

        # Stop ESP32 from resetting FPGA
        wifi_gpio0 = platform.request("wifi_gpio0")
        self.comb += wifi_gpio0.eq(1)

        ext0p = platform.request("ext0p")
        self.comb += ext0p.eq(sdram_ps_clk)
        ext1p = platform.request("ext1p")
        self.comb += ext1p.eq(self.cd_sys.clk)


class BaseSoC(SoCSDRAM):
    def __init__(self, **kwargs):
        platform = ulx3s.Platform(toolchain="prjtrellis")
        sys_clk_freq = int(50e6)
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
