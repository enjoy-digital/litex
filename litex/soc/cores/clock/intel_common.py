#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import DifferentialInput

from litex.soc.interconnect.csr import *

from litex.soc.cores.clock.common import *

# Intel / Generic ---------------------------------------------------------------------------------

class IntelClocking(Module, AutoCSR):
    def __init__(self, vco_margin=0):
        self.vco_margin = vco_margin
        self.reset      = Signal()
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
        config = {}
        for n in range(*self.n_div_range):
            config["n"] = n
            for m in reversed(range(*self.m_div_range)):
                all_valid = True
                vco_freq = self.clkin_freq*m/n
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if (vco_freq >= vco_freq_min*(1 + self.vco_margin) and
                    vco_freq <= vco_freq_max*(1 - self.vco_margin)):
                    for _n, (clk, f, p, _m) in sorted(self.clkouts.items()):
                        valid = False
                        for c in clkdiv_range(*self.c_div_range):
                            clk_freq = vco_freq/c
                            if abs(clk_freq - f) <= f*_m:
                                config["clk{}_freq".format(_n)]   = clk_freq
                                config["clk{}_divide".format(_n)] = c
                                config["clk{}_phase".format(_n)]  = p
                                valid = True
                                break
                            if valid:
                                break
                    if not valid:
                        all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"] = vco_freq
                    config["m"]   = m
                    compute_config_log(self.logger, config)
                    return config
        raise ValueError("No PLL config found")

    def do_finalize(self):
        assert hasattr(self, "clkin")
        config = self.compute_config()
        clks = Signal(self.nclkouts)
        self.params.update(
            p_BANDWIDTH_TYPE         = "AUTO",
            p_COMPENSATE_CLOCK       = "CLK0",
            p_INCLK0_INPUT_FREQUENCY = int(1e12/self.clkin_freq),
            p_OPERATION_MODE         = "NORMAL",
            i_INCLK                  = self.clkin,
            o_CLK                    = clks,
            i_ARESET                 = 0,
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
