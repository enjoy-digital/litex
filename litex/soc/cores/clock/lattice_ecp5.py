#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2021 George Hilliard <thirtythreeforty@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.soc.cores.clock.common import *

# Lattice / ECP5 -----------------------------------------------------------------------------------

class ECP5PLL(Module):
    nclkouts_max    = 4
    clki_div_range  = (1, 128+1)
    clkfb_div_range = (1, 128+1)
    clko_div_range  = (1, 128+1)
    clki_freq_range = (    8e6,  400e6)
    clko_freq_range = (3.125e6,  400e6)
    vco_freq_range  = (  400e6,  800e6)
    pfd_freq_range  = (   10e6,  400e6)

    def __init__(self):
        self.logger = logging.getLogger("ECP5PLL")
        self.logger.info("Creating ECP5PLL.")
        self.reset      = Signal()
        self.locked     = Signal()
        self.stdby      = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.dpa_en     = False
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

    def create_clkout(self, cd, freq, phase=0, margin=1e-2, with_reset=True, uses_dpa=True):
        (clko_freq_min, clko_freq_max) = self.clko_freq_range
        assert freq >= clko_freq_min
        assert freq <= clko_freq_max
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, phase, margin, uses_dpa)
        if with_reset:
            self.specials += AsyncResetSynchronizer(cd, ~self.locked)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        config = {}

        def in_range(n, r):
            (r_min, r_max) = r
            return n >= r_min and n <= r_max

        def found_clk(n, f, d, p):
            config["clko{}_freq".format(n)]  = f
            config["clko{}_div".format(n)]   = d
            config["clko{}_phase".format(n)] = p

        for clki_div in range(*self.clki_div_range):
            if not in_range(self.clkin_freq / clki_div, self.pfd_freq_range):
                continue
            config["clki_div"] = clki_div

            for clkfb_div in range(*self.clkfb_div_range):
                # pick a suitable feedback clock
                found_fb = None
                for n, (clk, f, p, m, dpa) in sorted(self.clkouts.items()):
                    if dpa and self.dpa_en:
                        # cannot use clocks whose phase the user will change
                        continue
                    for d in range(*self.clko_div_range):
                        vco_freq = self.clkin_freq/clki_div*clkfb_div*d
                        clk_freq = vco_freq/d
                        if in_range(vco_freq, self.vco_freq_range) \
                            and abs(clk_freq - f) <= f*m:
                            found_fb = n
                            found_clk(n, f, d, p)
                            break
                    if found_fb is not None:
                        break
                else:
                    # none found, try to use a new output
                    for d in range(*self.clko_div_range):
                        vco_freq = self.clkin_freq/clki_div*clkfb_div*d
                        clk_freq = vco_freq/d
                        if self.nclkouts < self.nclkouts_max \
                            and in_range(vco_freq, self.vco_freq_range) \
                            and in_range(clk_freq, self.clko_freq_range):
                            found_fb = self.nclkouts
                            found_clk(found_fb, clk_freq, d, 0)
                            break
                    else:
                        continue

                # vco_freq is known, compute remaining clocks' output settings
                all_valid = True
                for n, (clk, f, p, m, dpa) in sorted(self.clkouts.items()):
                    if n == found_fb:
                        continue  # already picked this one
                    for d in range(*self.clko_div_range):
                        clk_freq = vco_freq/d
                        if abs(clk_freq - f) <= f*m:
                            found_clk(n, f, d, p)
                            break
                    else:
                        all_valid = False
                if all_valid:
                    if found_fb > self.nclkouts:
                        self.create_clkout(ClockDomain('feedback'), vco_freq / clkfb_div)
                    config["vco"] = vco_freq
                    config["clkfb"] = found_fb
                    config["clkfb_div"] = clkfb_div
                    compute_config_log(self.logger, config)
                    return config
        raise ValueError("No PLL config found")

    def expose_dpa(self):
        self.dpa_en     = True
        self.phase_sel  = Signal(2)
        self.phase_dir  = Signal()
        self.phase_step = Signal()
        self.phase_load = Signal()

        # # #

        self.params.update(
            p_DPHASE_SOURCE = "ENABLED",
            i_PHASESEL0     = self.phase_sel[0],
            i_PHASESEL1     = self.phase_sel[1],
            i_PHASEDIR      = self.phase_dir,
            i_PHASESTEP     = self.phase_step,
            i_PHASELOADREG  = self.phase_load
        )

    def do_finalize(self):
        config = self.compute_config()
        locked = Signal()
        n_to_l = {0: "P", 1: "S", 2: "S2", 3: "S3"}
        self.params.update(
            attr=[
                ("FREQUENCY_PIN_CLKI",     str(self.clkin_freq/1e6)),
                ("ICP_CURRENT",            "6"),
                ("LPF_RESISTOR",          "16"),
                ("MFG_ENABLE_FILTEROPAMP", "1"),
                ("MFG_GMCREF_SEL",         "2")],
            i_RST           = self.reset,
            i_CLKI          = self.clkin,
            i_STDBY         = self.stdby,
            o_LOCK          = locked,
            p_FEEDBK_PATH   = "INT_O{}".format(n_to_l[config['clkfb']]),
            p_CLKFB_DIV     = config["clkfb_div"],
            p_CLKI_DIV      = config["clki_div"]
        )
        self.comb += self.locked.eq(locked & ~self.reset)
        for n, (clk, f, p, m, dpa) in sorted(self.clkouts.items()):
            div    = config["clko{}_div".format(n)]
            cphase = int(p*(div + 1)/360 + div - 1)
            self.params["p_CLKO{}_ENABLE".format(n_to_l[n])] = "ENABLED"
            self.params["p_CLKO{}_DIV".format(n_to_l[n])]    = div
            self.params["p_CLKO{}_FPHASE".format(n_to_l[n])] = 0
            self.params["p_CLKO{}_CPHASE".format(n_to_l[n])] = cphase
            self.params["o_CLKO{}".format(n_to_l[n])]        = clk
        self.specials += Instance("EHXPLLL", **self.params)
