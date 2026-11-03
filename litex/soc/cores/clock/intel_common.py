#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *

from litex.gen import *

from litex.soc.interconnect.csr import *

from litex.soc.cores.clock.common import *

# Intel / Generic ---------------------------------------------------------------------------------

class IntelClocking(LiteXModule):
    def __init__(self, vco_margin=0):
        check_margin(vco_margin, "VCO margin")
        self.vco_margin = vco_margin
        self.reset      = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}
        self.dpa_clkout = None

    def register_clkin(self, clkin, freq):
        check_freq_range(freq, self.clkin_freq_range, "Input clock frequency")
        self.clkin = connect_clkin(self, clkin, differential=True)
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, margin=1e-2, with_reset=True):
        check_freq_range(freq, self.clko_freq_range, "Output clock frequency")
        check_margin(margin)
        check_clkout_cd_unused(self, cd)
        check_clkout_count(self.nclkouts, self.nclkouts_max)
        clkout = Signal()
        self.clkouts[self.nclkouts] = ClkOut(clkout, freq, phase, margin)
        connect_clkout(self, cd, clkout, reset=~self.locked, with_reset=with_reset)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        check_clkin_registered(hasattr(self, "clkin"))
        check_clkouts(self.nclkouts)
        best_config = None
        best_score  = None
        clkdiv_range_list = list(clkdiv_range(*self.c_div_range)) # for speed
        # Only test values of N (input clock divisor) which result in a PFD
        # input frequency within the allowable range.
        min_n = math.ceil(self.clkin_freq/self.clkin_pfd_freq_range[1])
        max_n = math.floor(self.clkin_freq/self.clkin_pfd_freq_range[0])
        min_n = max(min_n, self.n_div_range[0]) # keep within counter size
        max_n = min(max_n+1, self.n_div_range[1])
        for n in range(min_n, max_n):
            for m in range(*self.m_div_range):
                # For this given N, M, check to see if we can meet requirements
                # for each clkout. If so, record the difference ratio from the
                # requested clock freqs.
                diff_ratios = [None] * len(self.clkouts)
                vco_freq = self.clkin_freq*m/n
                config = {"m": m, "vco": vco_freq}
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                # Dynamic phase shift: only VCOs with a whole-picosecond phase step (pinned in
                # Quartus with MANUAL_PHASE, see expose_dpa).
                dpa_ok = (self.dpa_clkout is None) or self._dpa_step_ok(vco_freq)
                if (dpa_ok and
                    vco_freq >= vco_freq_min*(1 + self.vco_margin) and
                    vco_freq <= vco_freq_max*(1 - self.vco_margin)):
                    clk_valid = [False] * len(self.clkouts)
                    for _n, clkout in sorted(self.clkouts.items()):
                        # For each C, see if the output frequency is within margin
                        # and the difference is better than the previous valid, best C.
                        best_diff = float("inf")
                        for c in clkdiv_range_list:
                            clk_freq = vco_freq/c
                            diff = abs(clk_freq - clkout.freq)
                            if diff <= clkout.freq*clkout.margin and diff < best_diff:
                                config[f"clk{_n}_freq"]   = clk_freq
                                config[f"clk{_n}_divide"] = c * n
                                config[f"clk{_n}_phase"]  = clkout.phase
                                clk_valid[_n] = True
                                diff_ratios[_n] = diff / clkout.freq
                                best_diff = diff
                    all_valid = all(clk_valid)
                else:
                    all_valid = False
                if all_valid:
                    best_config, best_score = update_best_config(best_config, best_score, config, diff_ratios, vco_freq)
        if best_config is not None:
            compute_config_log(self.logger, best_config)
            return best_config
        raise pll_config_error(self.clkin_freq, self.clkouts)

    # Dynamic phase shift (ALTPLL) ----------------------------------------------------------------

    # ALTPLL families with the PHASESTEP/PHASEUPDOWN/PHASECOUNTERSELECT/PHASEDONE ports.
    altpll_dpa = False

    @staticmethod
    def _dpa_step_ok(vco_freq):
        step_ps = 1e12/(8*vco_freq)
        return abs(step_ps - round(step_ps)) < 1e-3

    def expose_dpa(self, clkout, cd="sys"):
        """Expose the dynamic phase shift of one previously created output (ALTPLL).

        One step shifts the output by 1/8 of the VCO period. Hold phase_step high until
        phase_done goes low (at least 2 cycles of `cd`, the PLL's SCANCLK), then release it; the
        step is done when phase_done is back high. phase_dir: 1 shifts the output later, 0
        earlier. Use IntelPLLPhaseStepper for CSR control.

        Quartus picks its own VCO from the multiply/divide ratios; with the dynamic phase shift,
        the VCO search is limited to whole-picosecond steps and the step is pinned
        (VCO_FREQUENCY_CONTROL = MANUAL_PHASE), so dpa_steps() is the hardware's step count.
        """
        if not self.altpll_dpa:
            raise NotImplementedError(f"{type(self).__name__}: dynamic phase shift not supported.")
        if clkout not in self.clkouts:
            raise ValueError("Dynamic phase shift requires an existing clock output.")
        if self.dpa_clkout is not None:
            raise ValueError("Dynamic phase shift is already exposed.")
        self.dpa_clkout = clkout
        self.dpa_cd     = cd
        self.phase_step = Signal()
        self.phase_dir  = Signal()
        self.phase_done = Signal()

    def dpa_steps(self):
        """Phase steps per period of the dynamically shifted output."""
        config = self.compute_config()
        return round(8*config["vco"]/config[f"clk{self.dpa_clkout}_freq"])

    def add_reset_delay(self, cycles):
        for _ in range(cycles):
            reset = Signal()
            self.specials += Instance("DFFE", i_clk=self.clkin, i_d=self.reset, o_q=reset, i_ena=1, i_clrn=1, i_prn=1)
            self.reset = reset

    def do_finalize(self):
        check_clkin_registered(hasattr(self, "clkin"))
        self.add_reset_delay(cycles=8) # Prevents interlock when reset driven from sys_clk.
        config = self.compute_config()
        clks = Signal(self.nclkouts)
        self.params.update(
            p_BANDWIDTH_TYPE         = "AUTO",
            p_COMPENSATE_CLOCK       = "CLK0",
            p_INCLK0_INPUT_FREQUENCY = int(1e12/self.clkin_freq),
            p_OPERATION_MODE         = "NORMAL",
            i_INCLK                  = self.clkin,
            o_CLK                    = clks,
            i_ARESET                 = self.reset,
            i_CLKENA                 = 2**self.nclkouts_max - 1,
            i_EXTCLKENA              = 0xf,
            i_FBIN                   = 1,
            i_PFDENA                 = 1,
            i_PLLENA                 = 1,
            o_LOCKED                 = self.locked,
        )
        for n, clkout in sorted(self.clkouts.items()):
            clk_phase_ps = int((1e12/config[f"clk{n}_freq"])*config[f"clk{n}_phase"]/360)
            self.params[f"p_CLK{n}_DIVIDE_BY"]   = config[f"clk{n}_divide"]
            self.params[f"p_CLK{n}_DUTY_CYCLE"]  = 50
            self.params[f"p_CLK{n}_MULTIPLY_BY"] = config["m"]
            self.params[f"p_CLK{n}_PHASE_SHIFT"] = clk_phase_ps
            self.comb += clkout.clk.eq(clks[n])
        if self.dpa_clkout is not None:
            self.params.update(
                p_VCO_FREQUENCY_CONTROL   = "MANUAL_PHASE",
                p_VCO_PHASE_SHIFT_STEP    = round(1e12/(8*config["vco"])),
                p_PORT_PHASESTEP          = "PORT_USED",
                p_PORT_PHASEUPDOWN        = "PORT_USED",
                p_PORT_PHASECOUNTERSELECT = "PORT_USED",
                p_PORT_SCANCLK            = "PORT_USED",
                p_PORT_PHASEDONE          = "PORT_USED",
                i_PHASESTEP               = self.phase_step,
                i_PHASEUPDOWN             = self.phase_dir,
                i_PHASECOUNTERSELECT      = Constant(2 + self.dpa_clkout, 3), # 0: all, 1: M, 2+n: Cn.
                i_SCANCLK                 = ClockSignal(self.dpa_cd),
                o_PHASEDONE               = self.phase_done,
            )
        self.specials += Instance("ALTPLL", **self.params)

# Intel / ALTPLL Phase Stepper ---------------------------------------------------------------------

class IntelPLLPhaseStepper(LiteXModule):
    """CSR control of an ALTPLL output's dynamic phase shift (IntelClocking.expose_dpa).

    CSRs: `dir` (1: later), `step` (write: one step), `busy`, `position` (signed steps from the
    build-time phase) and `steps` (steps per period of the output). Named `sdram_clk_phase` in a
    SoC whose SDRAM clock comes from that output, it is used by the BIOS's SDRAM clock phase
    leveling (liblitedram sdram_clk_phase_leveling()).
    """
    def __init__(self, pll, timeout=255):
        assert pll.dpa_clkout is not None, "Call pll.expose_dpa() first."
        self._dpa_steps = pll.dpa_steps # Not the PLL itself: it would become a submodule.
        self.dir      = CSRStorage(1, reset=1, description="Step direction (1: later, 0: earlier).")
        self.step     = CSR() # Write: shift the output by one step.
        self.busy     = CSRStatus(description="A step is in progress.")
        self.position = CSRStatus(16, description="Signed steps from the build-time phase.")
        self.steps    = CSRStatus(16, description="Steps per period of the output.")

        # # #

        count    = Signal(max=timeout + 1)
        position = Signal((16, True))
        self.comb += pll.phase_dir.eq(self.dir.storage)
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(self.step.re,
                NextValue(count, 0),
                NextState("STEP")
            )
        )
        fsm.act("STEP",
            pll.phase_step.eq(1),
            NextValue(count, count + 1),
            If(((count >= 2) & ~pll.phase_done) | (count == timeout),
                NextValue(count, 0),
                NextState("WAIT")
            )
        )
        fsm.act("WAIT",
            NextValue(count, count + 1),
            If(pll.phase_done | (count == timeout),
                NextValue(position, position + Mux(self.dir.storage, 1, -1)),
                NextState("IDLE")
            )
        )
        self.comb += [
            self.busy.status.eq(~fsm.ongoing("IDLE")),
            self.position.status.eq(position),
        ]

    def do_finalize(self):
        self.comb += self.steps.status.eq(self._dpa_steps())
