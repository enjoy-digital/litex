#!/usr/bin/env python3

# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2014 Yann Sionneau <ys@m-labs.hk>
# License: BSD

import argparse
from fractions import Fraction

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.boards.platforms import minispartan6

from litex.soc.cores.clock import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import AS4C16M16
from litedram.phy import GENSDRPHY

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, clk_freq, use_s6pll=False):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain()

        # # #

        self.cd_sys.clk.attr.add("keep")
        self.cd_sys_ps.clk.attr.add("keep")

        if use_s6pll:
            self.submodules.pll = pll = S6PLL(speedgrade=-1)
            pll.register_clkin(platform.request("clk32"), 32e6)
            pll.create_clkout(self.cd_sys, clk_freq)
            pll.create_clkout(self.cd_sys_ps, clk_freq, phase=270)
        else:
            f0 = 32*1000000
            clk32 = platform.request("clk32")
            clk32a = Signal()
            self.specials += Instance("IBUFG", i_I=clk32, o_O=clk32a)
            clk32b = Signal()
            self.specials += Instance("BUFIO2", p_DIVIDE=1,
                                      p_DIVIDE_BYPASS="TRUE", p_I_INVERT="FALSE",
                                      i_I=clk32a, o_DIVCLK=clk32b)
            f = Fraction(int(clk_freq), int(f0))
            n, m, p = f.denominator, f.numerator, 8
            assert f0/n*m == clk_freq
            pll_lckd = Signal()
            pll_fb = Signal()
            pll = Signal(6)
            self.specials.pll = Instance("PLL_ADV", p_SIM_DEVICE="SPARTAN6",
                                         p_BANDWIDTH="OPTIMIZED", p_COMPENSATION="INTERNAL",
                                         p_REF_JITTER=.01, p_CLK_FEEDBACK="CLKFBOUT",
                                         i_DADDR=0, i_DCLK=0, i_DEN=0, i_DI=0, i_DWE=0, i_RST=0, i_REL=0,
                                         p_DIVCLK_DIVIDE=1, p_CLKFBOUT_MULT=m*p//n, p_CLKFBOUT_PHASE=0.,
                                         i_CLKIN1=clk32b, i_CLKIN2=0, i_CLKINSEL=1,
                                         p_CLKIN1_PERIOD=1000000000/f0, p_CLKIN2_PERIOD=0.,
                                         i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb, o_LOCKED=pll_lckd,
                                         o_CLKOUT0=pll[0], p_CLKOUT0_DUTY_CYCLE=.5,
                                         o_CLKOUT1=pll[1], p_CLKOUT1_DUTY_CYCLE=.5,
                                         o_CLKOUT2=pll[2], p_CLKOUT2_DUTY_CYCLE=.5,
                                         o_CLKOUT3=pll[3], p_CLKOUT3_DUTY_CYCLE=.5,
                                         o_CLKOUT4=pll[4], p_CLKOUT4_DUTY_CYCLE=.5,
                                         o_CLKOUT5=pll[5], p_CLKOUT5_DUTY_CYCLE=.5,
                                         p_CLKOUT0_PHASE=0., p_CLKOUT0_DIVIDE=p//1,
                                         p_CLKOUT1_PHASE=0., p_CLKOUT1_DIVIDE=p//1,
                                         p_CLKOUT2_PHASE=0., p_CLKOUT2_DIVIDE=p//1,
                                         p_CLKOUT3_PHASE=0., p_CLKOUT3_DIVIDE=p//1,
                                         p_CLKOUT4_PHASE=0., p_CLKOUT4_DIVIDE=p//1,  # sys
                                         p_CLKOUT5_PHASE=270., p_CLKOUT5_DIVIDE=p//1,  # sys_ps
            )
            self.specials += Instance("BUFG", i_I=pll[4], o_O=self.cd_sys.clk)
            self.specials += Instance("BUFG", i_I=pll[5], o_O=self.cd_sys_ps.clk)
            self.specials += AsyncResetSynchronizer(self.cd_sys, ~pll_lckd)

        self.specials += Instance("ODDR2", p_DDR_ALIGNMENT="NONE",
                                  p_INIT=0, p_SRTYPE="SYNC",
                                  i_D0=0, i_D1=1, i_S=0, i_R=0, i_CE=1,
                                  i_C0=self.cd_sys.clk, i_C1=~self.cd_sys.clk,
                                  o_Q=platform.request("sdram_clock"))

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCSDRAM):
    def __init__(self, sys_clk_freq=int(80e6), **kwargs):
        assert sys_clk_freq == int(80e6)
        platform = minispartan6.Platform()
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
                          integrated_rom_size=0x8000,
                          **kwargs)

        self.submodules.crg = _CRG(platform, sys_clk_freq)

        if not self.integrated_main_ram_size:
            self.submodules.sdrphy = GENSDRPHY(platform.request("sdram"))
            sdram_module = AS4C16M16(sys_clk_freq, "1:1")
            self.register_sdram(self.sdrphy,
                                sdram_module.geom_settings,
                                sdram_module.timing_settings)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on MiniSpartan6")
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
