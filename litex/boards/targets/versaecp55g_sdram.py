#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.boards.platforms import versaecp55g_sdram

from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import AS4C32M16
from litedram.phy import GENSDRPHY


class _CRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain()

        # # #

        clk100 = platform.request("clk100")
        rst_n = platform.request("rst_n")

        rst = Signal()
        self.comb += rst.eq(~rst_n)

        # sys_clk
        # FIXME: AsyncResetSynchronizer needs FD1S3BX support.
        #self.specials += AsyncResetSynchronizer(self.cd_sys, rst)
        self.comb += self.cd_sys.rst.eq(rst)
        self.comb += self.cd_sys_ps.rst.eq(rst)

        sys_clk = Signal()
        sdram_ps_clk = Signal()
        lock = Signal()

        self.specials += Instance(
            "EHXPLLL",
            i_CLKI=clk100,
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
            o_LOCK=lock,
            p_CLKOS_FPHASE=0,
            p_CLKOS_CPHASE=17,
            p_CLKOP_FPHASE=0,
            p_CLKOP_CPHASE=11,
            p_PLL_LOCK_MODE=0,
            p_OUTDIVIDER_MUXB="DIVB",
            p_OUTDIVIDER_MUXA="DIVA",
            p_CLKOS_ENABLE="ENABLED",
            p_CLKOP_ENABLE="ENABLED",
            p_CLKOS_DIV=12,
            p_CLKOP_DIV=12,
            p_CLKFB_DIV=1,
            p_CLKI_DIV=2,
            p_FEEDBK_PATH="CLKOP",
            attr=[("ICP_CURRENT", "12"), ("LPF_RESISTOR", "8"), ("MFG_ENABLE_FILTEROPAMP", "1"), ("MFG_GMCREF_SEL", "2")]
        )

        self.comb += self.cd_sys.clk.eq(sys_clk)
        self.comb += self.cd_sys_ps.clk.eq(sdram_ps_clk)
        sdram_clock = platform.request("sdram_clock")
        self.comb += sdram_clock.eq(sdram_ps_clk)
        led0 = platform.request("user_led", 0)
        self.comb += led0.eq(~lock)


class BaseSoC(SoCSDRAM):
    def __init__(self, **kwargs):
        platform = versaecp55g_sdram.Platform(toolchain="prjtrellis")
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
                                sdram_module.timing_settings)


def main():
    parser = argparse.ArgumentParser(description="LiteX SoC port to the ECP5 Versa board with SDRAM hat")
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
