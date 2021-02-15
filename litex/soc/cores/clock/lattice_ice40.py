#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.soc.cores.clock.common import *

# Lattice / iCE40 ----------------------------------------------------------------------------------

# TODO:
# - add phase support.
# - add support for GENCLK_HALF to be able to generate clock down to 8MHz.

class iCE40PLL(Module):
    nclkouts_max = 1
    divr_range = (0,  16)
    divf_range = (0, 128)
    divq_range = (0,   7)
    clki_freq_range = ( 10e6,  133e9)
    clko_freq_range = ( 16e6,  275e9)
    vco_freq_range  = (533e6, 1066e6)

    def __init__(self, primitive="SB_PLL40_CORE"):
        assert primitive in ["SB_PLL40_CORE", "SB_PLL40_PAD"]
        self.logger = logging.getLogger("iCE40PLL")
        self.logger.info("Creating iCE40PLL, {} primitive.".format(colorer(primitive)))
        self.primitive  = primitive
        self.reset      = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}

    def register_clkin(self, clkin, freq):
        (clki_freq_min, clki_freq_max) = self.clki_freq_range
        assert freq >= clki_freq_min
        assert freq <= clki_freq_max
        self.clkin = Signal()
        if isinstance(clkin, (Signal, ClockSignal)):
            self.comb += self.clkin.eq(clkin)
        else:
            raise ValueError
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, margin=1e-2, with_reset=True):
        (clko_freq_min, clko_freq_max) = self.clko_freq_range
        assert freq >= clko_freq_min
        assert freq <= clko_freq_max
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, 0, margin)
        if with_reset:
            self.specials += AsyncResetSynchronizer(cd, ~self.locked)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        config = {}
        for divr in range(*self.divr_range):
            for divf in range(*self.divf_range):
                all_valid = True
                vco_freq = self.clkin_freq/(divr + 1)*(divf +  1)
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if vco_freq >= vco_freq_min and vco_freq <= vco_freq_max:
                    for n, (clk, f, p, m) in sorted(self.clkouts.items()):
                        valid = False
                        for divq in range(*self.divq_range):
                            clk_freq = vco_freq/(2**divq)
                            if abs(clk_freq - f) <= f*m:
                                config["clkout_freq"] = clk_freq
                                config["divq"]        = divq
                                valid = True
                                break
                        if not valid:
                            all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"] = vco_freq
                    config["divr"] = divr
                    config["divf"] = divf
                    compute_config_log(self.logger, config)
                    return config
        raise ValueError("No PLL config found")

    def do_finalize(self):
        config = self.compute_config()
        clkfb = Signal()
        for f, v in [(17e6, 1), (26e6, 2), (44e6, 3), (66e6, 4), (101e6, 5), (133e6, 6)]:
            pfd_freq = self.clkin_freq/(config["divr"] + 1)
            if pfd_freq < f:
                filter_range = v
                break
        self.params.update(
            p_FEEDBACK_PATH = "SIMPLE",
            p_FILTER_RANGE  = filter_range,
            i_RESETB        = ~self.reset,
            o_LOCK          = self.locked,
        )
        if self.primitive == "SB_PLL40_CORE":
            self.params.update(i_REFERENCECLK=self.clkin)
        if self.primitive == "SB_PLL40_PAD":
            self.params.update(i_PACKAGEPIN=self.clkin)
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            self.params["p_DIVR"]         = config["divr"]
            self.params["p_DIVF"]         = config["divf"]
            self.params["p_DIVQ"]         = config["divq"]
            self.params["o_PLLOUTGLOBAL"] = clk
        self.specials += Instance(self.primitive, **self.params)
