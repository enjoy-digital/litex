#
# This file is part of LiteX.
#
# Copyright (c) 2023 Gwenhael Goavec-merou<gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

from litex.soc.cores.clock.common import *

# CologneChip GateMate CC_PLL ---------------------------------------------------------------------

class GateMatePLL(LiteXModule):
    """
    CC_PLL generator for CologneChip GateMate FPGAs (UG1001 7.3)
    Parameters
    ----------
    perf_mode: str
        FPGA operation mode for VDD_PLL (UNDEFINED, LOWPOWER, ECONOMY, SPEED) (default: UNDEFINED)
    low_jitter: int
        Low Jitter Mode (0,1) (default: 1)
    lock_req: int
        Lock status required before PLL output enable (0,1) (default: 1)

    Attributes
    ----------
    reset: Signal in
    locked: Signal out
    """

    def __init__(self,
        perf_mode  = "undefined",
        low_jitter = 1,
        lock_req   = 1):

        assert perf_mode.lower() in ["undefined", "lowpower", "economy", "speed"]
        assert low_jitter in [0, 1]
        assert lock_req in [0, 1]

        self.logger      = logging.getLogger("CC_PLL")
        self.reset       = Signal()
        self.locked      = Signal()
        self._clkin_freq = None
        self._clkouts    = {}
        self._perf_mode  = perf_mode.upper()
        self._low_jitter = low_jitter
        self._lock_req   = lock_req

        self._max_freq   = {
            "undefined" : 250e6,
            "lowpower"  : 250e6,
            "economy"   : 312.5e6,
            "speed"     : 416.75e6
        }[perf_mode.lower()]

    def register_clkin(self, clkin, freq, usr_clk_ref=False):
        """
        Register clkin signal as input PLL input signal
        Parameters
        ----------
        clkin: ClockSignal / Signal
            input clock signal
        freq: float
            input clock frequency (Hz)
        usr_clk_ref: bool
            select if clkin is connected to CLK_REF or USR_CLK_REF
        """
        self._usr_clk_ref = usr_clk_ref
        self._clkin = Signal()
        if isinstance(clkin, (Signal, ClockSignal)):
            self.comb += self._clkin.eq(clkin)
        else:
            raise ValueError
        self._clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, with_reset=True):
        """
        Register cd ClockDomain as PLL output signal
        Parameters
        ----------
        cd: ClockDomain
            input clock signal
        freq: float
            output clock frequency (Hz)
        phase: int
            must be 0, 90, 180, 270
        with_reset: bool
            drive cd reset
        """
        assert phase in [0, 90, 180, 270]
        assert phase not in self._clkouts
        assert freq <= self._max_freq

        clkout = Signal()
        self._clkouts[phase] = (clkout, freq)
        if with_reset:
            self.specials += AsyncResetSynchronizer(cd, ~self.locked)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, 0, phase)

    def do_finalize(self):
        assert hasattr(self, "_clkin")
        assert len(self._clkouts) > 0

        # set/unset frequency doubler for CLK180/CLK270
        clk_doub    = {180:0, 270:0}
        # extract slowest frequency -> ref
        clkout_freq = min([f for (_, f) in self._clkouts.values()])

        for phase in [0, 90, 180, 270]:
            (clk, freq) = self._clkouts.get(phase, (Open(), 0))
            self._clkouts[phase] = (clk, freq) # force update (add unselected output)
            if freq != 0:
                # clk0 and clk90 frequency must be equal to clkout freq
                if phase in [0, 90]:
                    assert freq == clkout_freq
                else:
                    # clk180 and clk270 must be x1 or x2 clkout frequency
                    assert freq in [clkout_freq, 2 * clkout_freq]
                    # when clk180 or clk270 == x2 clkout: CLKxx_DOUB must be set
                    if freq == 2 * clkout_freq:
                        clk_doub[phase] = 1

        assert clkout_freq is not None

        freqInMHz  = self._clkin_freq/1e6
        freqOutMHz = clkout_freq/1e6

        self.specials += Instance("CC_PLL",
            p_REF_CLK             = str(freqInMHz),   # reference input in MHz
            p_OUT_CLK             = str(freqOutMHz),  # pll output frequency in MHz
            p_LOW_JITTER          = self._low_jitter, # 0: disable, 1: enable low jitter mode
            p_PERF_MD             = self._perf_mode,  # FPGA operation mode for VDD_PLL
            p_LOCK_REQ            = self._lock_req,   # Lock status required before PLL output enable
            p_CI_FILTER_CONST     = 2,                # optional CI filter constant
            p_CP_FILTER_CONST     = 4,                # optional CP filter constant
            i_CLK_REF             = self._clkin if not self._usr_clk_ref else Open(),
            i_USR_CLK_REF         = self._clkin if self._usr_clk_ref else Open(),
            i_CLK_FEEDBACK        = 0,
            i_USR_LOCKED_STDY_RST = self.reset,
            o_CLK_REF_OUT         = Open(),
            o_USR_PLL_LOCKED_STDY = self.locked,
            o_USR_PLL_LOCKED      = Open(),
            **{f"o_CLK{p}"        : c for (p, (c, _)) in self._clkouts.items()},
            **{f"p_CLK{p}_DOUB"   : v for (p, v) in clk_doub.items()},
        )

