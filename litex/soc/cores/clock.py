"""
Clock Abstraction Modules


Made in Paris-CDG while waiting a delayed Air-France KLM flight...
"""

from migen import *
from migen.genlib.io import DifferentialInput
from migen.genlib.resetsync import AsyncResetSynchronizer


def period_ns(freq):
    return 1e9/freq


class S7Clocking(Module):
    clkin_freq_range = (10e6, 800e6)
    clkfbout_mult_frange = (2, 64+1)
    clkout_divide_range = (1, 128+1)

    def __init__(self, speedgrade=-1):
        if speedgrade == -3:
            self.vco_freq_range = (600e6, 1600e6)
        elif speedgrade == -2:
            self.vco_freq_range = (600e6, 1440e6)
        else:
            self.vco_freq_range = (600e6, 1200e6)

        self.reset = Signal()
        self.locked = Signal()
        self.clkin_freq = None
        self.vcxo_freq = None
        self.nclkouts = 0
        self.clkouts = {}
        self.config = {}

    def register_clkin(self, clkin, freq):
        self.clkin = Signal()
        if isinstance(clkin, Signal):
            self.comb += self.clkin.eq(clkin)
        elif isinstance(clkin, Record):
            self.specials += DifferentialInput(clkin.p, clkin.n, self.clkin)
        else:
            raise ValueError
        self.clkin_freq = freq

    def create_clkout(self, cd, freq, phase=0):
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        clkout_bufg = Signal()
        self.specials += AsyncResetSynchronizer(cd, ~self.locked | self.reset),
        self.specials += Instance("BUFG", i_I=clkout, o_O=clkout_bufg)
        self.comb += cd.clk.eq(clkout_bufg)
        self.clkouts[self.nclkouts] = (clkout, freq, phase)
        self.nclkouts += 1
        return clkout_bufg

    def compute_config(self):
        config = {}
        config["divclk_divide"] = 1
        for clkfbout_mult in range(*self.clkfbout_mult_frange):
            all_valid = True
            vco_freq = self.clkin_freq*clkfbout_mult
            (vco_freq_min, vco_freq_max) = self.vco_freq_range
            if vco_freq >= vco_freq_min and vco_freq <= vco_freq_max:
                for n, (clk, f, p) in sorted(self.clkouts.items()):
                    valid = False
                    for d in range(*self.clkout_divide_range):
                        clk_freq = vco_freq/d
                        if clk_freq == f:
                            config["clkout{}_divide".format(n)] = d
                            config["clkout{}_phase".format(n)] = p
                            valid = True
                            break
                    if not valid:
                        all_valid = False
            else:
                all_valid = False
            if all_valid:
                config["vco"] = vco_freq
                config["clkfbout_mult"] = clkfbout_mult
                return config
        raise ValueError("No PLL config found")

    def add_idelayctrl(self, cd):
        reset_counter = Signal(4, reset=15)
        ic_reset = Signal(reset=1)
        sync = getattr(self.sync, cd.name)
        sync += \
            If(reset_counter != 0,
                reset_counter.eq(reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        self.specials += Instance("IDELAYCTRL", i_REFCLK=cd.clk, i_RST=ic_reset)

    def do_finalize(self):
        assert hasattr(self, "clkin")


class S7PLL(S7Clocking):
    nclkouts_max = 6

    def do_finalize(self):
        S7Clocking.do_finalize(self)
        config = self.compute_config()
        pll_fb = Signal()
        pll_params = dict(
            p_STARTUP_WAIT="FALSE", i_RST=self.reset, o_LOCKED=self.locked,

            # VCO
            p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=period_ns(self.clkin_freq),
            p_CLKFBOUT_MULT=config["clkfbout_mult"], p_DIVCLK_DIVIDE=config["divclk_divide"],
            i_CLKIN1=self.clkin, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,
        )
        for n, (clk, f, p) in sorted(self.clkouts.items()):
            pll_params["p_CLKOUT{}_DIVIDE".format(n)] = config["clkout{}_divide".format(n)]
            pll_params["p_CLKOUT{}_PHASE".format(n)] = config["clkout{}_phase".format(n)]
            pll_params["o_CLKOUT{}".format(n)] = clk
        self.specials += Instance("PLLE2_BASE", **pll_params)


class S7MMCM(S7Clocking):
    nclkouts_max = 7

    def do_finalize(self):
        S7Clocking.do_finalize(self)
        config = self.compute_config()
        mmcm_fb = Signal()
        mmcm_params = dict(
            p_BANDWIDTH="OPTIMIZED", i_RST=self.reset, o_LOCKED=self.locked,

            # VCO
            p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=period_ns(self.clkin_freq),
            p_CLKFBOUT_MULT_F=config["clkfbout_mult"], p_DIVCLK_DIVIDE=config["divclk_divide"],
            i_CLKIN1=self.clkin, i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,
        )
        for n, (clk, f, p) in sorted(self.clkouts.items()):
            if n == 0:
                mmcm_params["p_CLKOUT{}_DIVIDE_F".format(n)] = config["clkout{}_divide".format(n)]
            else:
                mmcm_params["p_CLKOUT{}_DIVIDE".format(n)] = config["clkout{}_divide".format(n)]
            mmcm_params["p_CLKOUT{}_PHASE".format(n)] = config["clkout{}_phase".format(n)]
            mmcm_params["o_CLKOUT{}".format(n)] = clk
        self.specials += Instance("MMCME2_BASE", **mmcm_params)
