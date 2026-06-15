#
# This file is part of LiteX.
#
# Copyright (c) 2018-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.cores.clock.common import *

# Lattice / iCE40 ----------------------------------------------------------------------------------

# TODO:
# - add phase support.
# - add support for GENCLK_HALF to be able to generate clock down to 8MHz.

class iCE40PLL(LiteXModule):
    nclkouts_max = 1
    divr_range = (0,  16)
    divf_range = (0, 128)
    divq_range = (0,   7)
    clki_freq_range = ( 10e6,  133e6)
    clko_freq_range = ( 16e6,  275e6)
    vco_freq_range  = (533e6, 1066e6)

    def __init__(self, primitive="SB_PLL40_CORE", name=None):
        if primitive not in ["SB_PLL40_CORE", "SB_PLL40_PAD"]:
            raise ValueError("Unsupported iCE40 PLL primitive: {}.".format(primitive))
        self.logger = logging.getLogger("iCE40PLL")
        self.logger.info("Creating iCE40PLL, {} primitive.".format(colorer(primitive)))
        self.primitive  = primitive
        self.name       = name
        self.reset      = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}

    def register_clkin(self, clkin, freq):
        check_freq_range(freq, self.clki_freq_range, "Input clock frequency")
        self.clkin = connect_clkin(self, clkin)
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, margin=1e-2, with_reset=True):
        check_freq_range(freq, self.clko_freq_range, "Output clock frequency")
        check_margin(margin)
        check_clkout_cd_unused(self, cd)
        check_clkout_count(self.nclkouts, self.nclkouts_max)
        clkout = Signal()
        self.clkouts[self.nclkouts] = ClkOut(clkout, freq, 0, margin)
        connect_clkout(self, cd, clkout, reset=~self.locked, with_reset=with_reset)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        check_clkin_registered(hasattr(self, "clkin"))
        check_clkouts(self.nclkouts)
        best_config = None
        best_score  = None
        for divr in range(*self.divr_range):
            for divf in range(*self.divf_range):
                all_valid = True
                errors    = []
                config    = {}
                vco_freq = self.clkin_freq/(divr + 1)*(divf +  1)
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if vco_freq >= vco_freq_min and vco_freq <= vco_freq_max:
                    for n, clkout in sorted(self.clkouts.items()):
                        best_clkout = clkout_best_divider(
                            clkout.freq,
                            clkout.margin,
                            range(*self.divq_range),
                            lambda divq: vco_freq/(2**divq)
                        )
                        if best_clkout is None:
                            all_valid = False
                            break
                        error, clk_freq, divq = best_clkout
                        errors.append(error)
                        config["clkout_freq"] = clk_freq
                        config["divq"]        = divq
                else:
                    all_valid = False
                if all_valid:
                    config["vco"] = vco_freq
                    config["divr"] = divr
                    config["divf"] = divf
                    best_config, best_score = update_best_config(best_config, best_score, config, errors, vco_freq)
        if best_config is not None:
            compute_config_log(self.logger, best_config)
            return best_config
        raise pll_config_error(self.clkin_freq, self.clkouts)

    def do_finalize(self):
        config = self.compute_config()
        clkfb = Signal()
        for f, v in [(17e6, 1), (26e6, 2), (44e6, 3), (66e6, 4), (101e6, 5), (133e6, 6)]:
            pfd_freq = self.clkin_freq/(config["divr"] + 1)
            if pfd_freq <= f:
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
        for n, clkout in sorted(self.clkouts.items()):
            self.params["p_DIVR"]         = config["divr"]
            self.params["p_DIVF"]         = config["divf"]
            self.params["p_DIVQ"]         = config["divq"]
            self.params["o_PLLOUTGLOBAL"] = clkout.clk
        self.specials += Instance(self.primitive, name=self.name or "", **self.params)
