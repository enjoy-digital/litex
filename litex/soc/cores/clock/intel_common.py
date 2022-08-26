#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

#file to be placed in litex/litex/soc/cores/clock directory. Some enhancement on resetting the pll

from operator import mul
from functools import reduce

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import DifferentialInput

from litex.soc.interconnect.csr import *

from litex.soc.cores.clock.common import *

# Intel / Generic ---------------------------------------------------------------------------------

def geometric_mean(vals):
    return reduce(mul, vals, 1) ** (1 / len(vals))


class IntelClocking(Module, AutoCSR):
    def __init__(self, vco_margin=0):
        self.vco_margin = vco_margin
        self.pll_reset  = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}

    def register_clkin(self, clkin, freq):
        self.clkin = Signal()
        if isinstance(clkin, (Signal, ClockSignal)):
            self.comb += self.clkin.eq(clkin)
        elif isinstance(clkin, Record):
            self.specials += DifferentialInput(clkin.p, clkin.n, self.clkin)
        else:
            raise ValueError
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, margin=1e-2, with_reset=True):
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, phase, margin)
        if with_reset:
            self.specials += AsyncResetSynchronizer(cd, ~self.locked)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        valid_configs = {}
        for n in range(*self.n_div_range):
            for m in range(*self.m_div_range):
                # For this given N, M, check to see if we can meet requirements
                # for each clkout. If so, record the difference ratio from the
                # requested clock freqs.
                diff_ratios = [None] * len(self.clkouts)
                vco_freq = self.clkin_freq*m/n
                config = {"m": m, "vco": vco_freq}
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if (vco_freq >= vco_freq_min*(1 + self.vco_margin) and
                    vco_freq <= vco_freq_max*(1 - self.vco_margin)):
                    clk_valid = [False] * len(self.clkouts)
                    for _n, (clk, f, p, _m) in sorted(self.clkouts.items()):
                        # For each C, see if the output frequency is within margin
                        # and the difference is better than the previous valid, best C.
                        best_diff = float("inf")
                        for c in clkdiv_range(*self.c_div_range):
                            clk_freq = vco_freq/c
                            diff = abs(clk_freq - f)
                            if diff <= f*_m and diff < best_diff:
                                config[f"clk{_n}_freq"]   = clk_freq
                                config[f"clk{_n}_divide"] = c * n
                                config[f"clk{_n}_phase"]  = p
                                clk_valid[_n] = True
                                diff_ratios[_n] = diff / f
                                best_diff = diff
                    all_valid = all(clk_valid)
                else:
                    all_valid = False
                if all_valid:
                    valid_configs[geometric_mean(diff_ratios)] = config
        if len(valid_configs):
            best_config = sorted(valid_configs.items())[0][1]
            compute_config_log(self.logger, best_config)
            return best_config
        raise ValueError("No PLL config found")

    def do_finalize(self):
        assert hasattr(self, "clkin")
        config = self.compute_config()
        clks = Signal(self.nclkouts_max)
        self.params.update(
            p_BANDWIDTH_TYPE         = "AUTO",
            p_COMPENSATE_CLOCK       = "CLK0",
            p_INCLK0_INPUT_FREQUENCY = int(1e12/self.clkin_freq),
            p_OPERATION_MODE         = "NORMAL",
            i_INCLK                  = Cat(self.clkin, 0),
            o_CLK                    = clks,
            i_ARESET                 = self.pll_reset,
            i_CLKENA                 = 2**self.nclkouts_max - 1,
            i_EXTCLKENA              = 0xf,
            i_FBIN                   = 1,
            i_PFDENA                 = 1,
            i_PLLENA                 = 1,
            o_LOCKED                 = self.locked,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            clk_phase_ps = int((1e12/config["clk{}_freq".format(n)])*config["clk{}_phase".format(n)]/360)
            self.params["p_CLK{}_DIVIDE_BY".format(n)]   = config["clk{}_divide".format(n)]
            self.params["p_CLK{}_DUTY_CYCLE".format(n)]  = 50
            self.params["p_CLK{}_MULTIPLY_BY".format(n)] = config["m"]
            self.params["p_CLK{}_PHASE_SHIFT".format(n)] = clk_phase_ps
            self.comb += clk.eq(clks[n])
        self.specials += Instance("ALTPLL", **self.params)
