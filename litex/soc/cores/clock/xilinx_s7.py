#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.xilinx_common import *

# Xilinx / 7-Series --------------------------------------------------------------------------------

class S7PLL(XilinxClocking):
    nclkouts_max = 6
    clkin_freq_range = (19e6, 800e6)

    def __init__(self, speedgrade=-1):
        self.logger = logging.getLogger("S7PLL")
        self.logger.info("Creating S7PLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 56+1)
        self.vco_freq_range = {
            -1: (800e6, 1600e6),
            -2: (800e6, 1866e6),
            -3: (800e6, 2133e6),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        pll_fb = Signal()
        self.params.update(
            # Global.
            p_STARTUP_WAIT = "FALSE",
            i_RST          = self.reset,
            i_PWRDWN       = self.power_down,
            o_LOCKED       = self.locked,

            # VCO.
            p_REF_JITTER1   = 0.01,
            p_CLKIN1_PERIOD = 1e9/self.clkin_freq,
            p_CLKFBOUT_MULT = config["clkfbout_mult"],
            p_DIVCLK_DIVIDE = config["divclk_divide"],
            i_CLKIN1        = self.clkin,
            i_CLKFBIN       = pll_fb,
            o_CLKFBOUT      = pll_fb,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            self.params["p_CLKOUT{}_DIVIDE".format(n)] = config["clkout{}_divide".format(n)]
            self.params["p_CLKOUT{}_PHASE".format(n)] = config["clkout{}_phase".format(n)]
            self.params["o_CLKOUT{}".format(n)] = clk
        self.specials += Instance("PLLE2_ADV", **self.params)


class S7MMCM(XilinxClocking):
    nclkouts_max         = 7
    clkout0_divide_range = (1, (128 + 1/8), 1/8) # Fractional Divide available on CLKOUT0

    def __init__(self, speedgrade=-1):
        self.logger = logging.getLogger("S7MMCM")
        self.logger.info("Creating S7MMCM, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 106+1)
        self.clkin_freq_range = {
            -1: (10e6,  800e6),
            -2: (10e6,  933e6),
            -3: (10e6, 1066e6),
        }[speedgrade]

        self.vco_freq_range = {
            -1: (600e6, 1200e6),
            -2: (600e6, 1440e6),
            -3: (600e6, 1600e6),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        mmcm_fb = Signal()
        self.params.update(
            # Global.
            p_BANDWIDTH = "OPTIMIZED",
            i_RST       = self.reset,
            i_PWRDWN    = self.power_down,
            o_LOCKED    = self.locked,

            # VCO.
            p_REF_JITTER1     = 0.01,
            p_CLKIN1_PERIOD   = 1e9/self.clkin_freq,
            p_CLKFBOUT_MULT_F = config["clkfbout_mult"],
            p_DIVCLK_DIVIDE   = config["divclk_divide"],
            i_CLKIN1          = self.clkin,
            i_CLKFBIN         = mmcm_fb,
            o_CLKFBOUT        = mmcm_fb,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            if n == 0:
                self.params["p_CLKOUT{}_DIVIDE_F".format(n)] = config["clkout{}_divide".format(n)]
            else:
                self.params["p_CLKOUT{}_DIVIDE".format(n)] = config["clkout{}_divide".format(n)]
            self.params["p_CLKOUT{}_PHASE".format(n)] = config["clkout{}_phase".format(n)]
            self.params["o_CLKOUT{}".format(n)]       = clk
        self.specials += Instance("MMCME2_ADV", **self.params)


class S7IDELAYCTRL(Module):
    def __init__(self, cd, reset_cycles=16):
        reset_counter = Signal(log2_int(reset_cycles), reset=reset_cycles - 1)
        ic_reset      = Signal(reset=1)
        sync = getattr(self.sync, cd.name)
        sync += \
            If(reset_counter != 0,
                reset_counter.eq(reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        self.specials += Instance("IDELAYCTRL", i_REFCLK=cd.clk, i_RST=ic_reset)
