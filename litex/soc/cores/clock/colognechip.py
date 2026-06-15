#
# This file is part of LiteX.
#
# Copyright (c) 2023 Gwenhael Goavec-merou<gwenhael.goavec-merou@trabucayre.com>
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

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
        lock_req   = 1,
        name       = None):

        if not isinstance(perf_mode, str) or perf_mode.lower() not in ["undefined", "lowpower", "economy", "speed"]:
            raise ValueError("Unsupported PLL performance mode: {}.".format(perf_mode))
        if low_jitter not in [0, 1]:
            raise ValueError("PLL low_jitter must be 0 or 1.")
        if lock_req not in [0, 1]:
            raise ValueError("PLL lock_req must be 0 or 1.")

        self.logger      = logging.getLogger("CC_PLL")
        self.reset       = Signal()
        self.locked      = Signal()
        self._clkin_freq = None
        self._clkouts    = {}
        self._perf_mode  = perf_mode.upper()
        self._low_jitter = low_jitter
        self._lock_req   = lock_req
        self.name        = name

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
        check_freq_positive(freq, "Input clock frequency")
        self._usr_clk_ref = usr_clk_ref
        self._clkin = connect_clkin(self, clkin)
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
        check_phase_allowed(phase, [0, 90, 180, 270])
        check_clkout_cd_unused(self, cd)
        if phase in self._clkouts:
            raise ValueError("Output clock phase {} is already used.".format(phase))
        check_freq_range(freq, (0, self._max_freq), "Output clock frequency")

        clkout = Signal()
        self._clkouts[phase] = (clkout, freq)
        connect_clkout(self, cd, clkout, reset=~self.locked, with_reset=with_reset)
        create_clkout_log(self.logger, cd.name, freq, 0, phase)

    def do_finalize(self):
        if not hasattr(self, "_clkin"):
            raise ValueError("Input clock frequency has not been registered.")
        if len(self._clkouts) == 0:
            raise ValueError("At least one output clock must be registered.")

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
                    if freq != clkout_freq:
                        raise ValueError(
                            "CLK{} frequency must be equal to base output frequency.".format(phase)
                        )
                else:
                    # clk180 and clk270 must be x1 or x2 clkout frequency
                    if freq not in [clkout_freq, 2 * clkout_freq]:
                        raise ValueError(
                            "CLK{} frequency must be equal to or twice base output frequency.".format(phase)
                        )
                    # when clk180 or clk270 == x2 clkout: CLKxx_DOUB must be set
                    if freq == 2 * clkout_freq:
                        clk_doub[phase] = 1

        freqInMHz  = self._clkin_freq/1e6
        freqOutMHz = clkout_freq/1e6

        locked_s1 = Signal()

        self.specials += Instance("CC_PLL", name=self.name or "",
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
            i_USR_LOCKED_STDY_RST = 0,
            o_CLK_REF_OUT         = Open(),
            o_USR_PLL_LOCKED_STDY = Open(),
            o_USR_PLL_LOCKED      = locked_s1,
            **{f"o_CLK{p}"        : c for (p, (c, _)) in self._clkouts.items()},
            **{f"p_CLK{p}_DOUB"   : v for (p, v) in clk_doub.items()},
        )

        self.comb += self.locked.eq(locked_s1 & ~self.reset)
