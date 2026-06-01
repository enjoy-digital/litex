#
# This file is part of LiteX.
#
# Copyright (c) 2018-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2021 George Hilliard <thirtythreeforty@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.cores.clock.common import *

# Lattice / ECP5 PLL -------------------------------------------------------------------------------

class ECP5PLL(LiteXModule):
    nclkouts_max    = 4
    clki_div_range  = (1, 128+1)
    clkfb_div_range = (1, 128+1)
    clko_div_range  = (1, 128+1)
    clki_freq_range = (    8e6,  400e6)
    clko_freq_range = (3.125e6,  400e6)
    vco_freq_range  = (  400e6,  800e6)
    pfd_freq_range  = (   10e6,  400e6)

    def __init__(self, bel=None, name=None):
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
        self.bel        = bel
        self.name       = name

    def register_clkin(self, clkin, freq):
        check_freq_range(freq, self.clki_freq_range, "Input clock frequency")
        self.clkin = connect_clkin(self, clkin)
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, margin=1e-2, with_reset=True, uses_dpa=True):
        check_freq_range(freq, self.clko_freq_range, "Output clock frequency")
        check_margin(margin)
        check_clkout_cd_unused(self, cd)
        check_clkout_count(self.nclkouts, self.nclkouts_max)
        clkout = Signal()
        self.clkouts[self.nclkouts] = ClkOutDPA(clkout, freq, phase, margin, uses_dpa)
        connect_clkout(self, cd, clkout, reset=~self.locked, with_reset=with_reset)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        check_clkin_registered(hasattr(self, "clkin"))
        check_clkouts(self.nclkouts)
        best_config            = None
        best_score             = None
        best_feedback_clkout   = None
        active_clkouts         = {n: clkout for n, clkout in self.clkouts.items() if clkout.freq > 0}
        feedback_only_clkouts  = [n for n, clkout in self.clkouts.items() if clkout.freq == 0]
        # Iterate on CLKI dividers...
        for clki_div in range(*self.clki_div_range):
            # Check if in PFD range.
            (pfd_freq_min, pfd_freq_max) = self.pfd_freq_range
            if not (pfd_freq_min <= self.clkin_freq/clki_div <= pfd_freq_max):
                continue
            # Iterate on CLKO dividers... (to get us in VCO range)
            for clkofb_div in range(*self.clko_div_range):
                # Iterate on CLKFB dividers...
                for clkfb_div in range(*self.clkfb_div_range):
                    errors   = []
                    config   = {"clki_div": clki_div}
                    vco_freq = (self.clkin_freq/clki_div)*clkfb_div*clkofb_div
                    (vco_freq_min, vco_freq_max) = self.vco_freq_range
                    all_valid = True
                    # If in VCO range, find dividers for all outputs.
                    if vco_freq_min <= vco_freq <= vco_freq_max:
                        config["clkfb"]  = None
                        clkout_configs   = {}
                        feedback_configs = {}
                        for n, clkout in sorted(active_clkouts.items()):
                            for d in range(*self.clko_div_range):
                                clk_freq = vco_freq/d
                                error    = clkout_freq_error(clk_freq, clkout.freq)
                                # Check if output can be used as feedback, if so save it.
                                # (We cannot use clocks with dynamic phase adjustment enabled)
                                if error <= clkout.margin and (d == clkofb_div) and (not (clkout.uses_dpa and self.dpa_en)):
                                    if n not in feedback_configs or error < feedback_configs[n][0]:
                                        feedback_configs[n] = (error, clk_freq, d, clkout.phase)
                            best_clkout = clkout_best_divider(
                                clkout.freq,
                                clkout.margin,
                                clkdiv_candidates([self.clko_div_range], ideal=vco_freq/clkout.freq),
                                lambda d: vco_freq/d
                            )
                            if best_clkout is None:
                                all_valid = False
                                break
                            error, clk_freq, d = best_clkout
                            clkout_configs[n]  = (error, clk_freq, d, clkout.phase)
                        if all_valid:
                            for n, (error, clk_freq, d, p) in sorted(clkout_configs.items()):
                                if n in feedback_configs and d == feedback_configs[n][2]:
                                    config["clkfb"] = n

                            if config["clkfb"] is None and self.nclkouts == self.nclkouts_max and not feedback_only_clkouts:
                                best_feedback_score  = None
                                best_feedback_clkout = None
                                for n, feedback_config in feedback_configs.items():
                                    candidate_clkouts    = dict(clkout_configs)
                                    candidate_clkouts[n] = feedback_config
                                    candidate_errors     = [clkout[0] for clkout in candidate_clkouts.values()]
                                    candidate_score      = clkout_config_score(candidate_errors, vco_freq)
                                    if best_feedback_score is None or candidate_score < best_feedback_score:
                                        best_feedback_score  = candidate_score
                                        best_feedback_clkout = n
                                if best_feedback_clkout is None:
                                    # If there is no output suitable for feedback and no spare, not valid
                                    all_valid = False
                                else:
                                    clkout_configs[best_feedback_clkout] = feedback_configs[best_feedback_clkout]
                                    config["clkfb"] = best_feedback_clkout

                        if all_valid:
                            errors = []
                            for n, (error, clk_freq, d, p) in sorted(clkout_configs.items()):
                                errors.append(error)
                                config["clko{}_freq".format(n)]  = clk_freq
                                config["clko{}_div".format(n)]   = d
                                config["clko{}_phase".format(n)] = p
                    else:
                        all_valid = False
                    if all_valid:
                        # If no output suitable for feedback, create a new output for it.
                        if config["clkfb"] is None:
                            # We need at least a free output...
                            if feedback_only_clkouts:
                                feedback_clkout = feedback_only_clkouts[0]
                            else:
                                feedback_clkout = self.nclkouts
                            config["clkfb"] = feedback_clkout
                            config[f"clko{feedback_clkout}_div"] = int((vco_freq*clki_div)/(self.clkin_freq*clkfb_div))
                        else:
                            feedback_clkout = None
                        config["vco"]       = vco_freq
                        config["clkfb_div"] = clkfb_div
                        best_config, new_score = update_best_config(best_config, best_score, dict(config), errors, vco_freq)
                        if new_score != best_score:
                            best_score           = new_score
                            best_feedback_clkout = feedback_clkout
        if best_config is not None:
            if best_feedback_clkout is not None and best_feedback_clkout not in self.clkouts:
                self.clkouts[best_feedback_clkout] = ClkOutDPA(Signal(), 0, 0, 0, 0)
            compute_config_log(self.logger, best_config)
            return best_config
        raise pll_config_error(self.clkin_freq, self.clkouts)

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
            p_FEEDBK_PATH   = f"INT_O{n_to_l[config['clkfb']]}",
            p_CLKFB_DIV     = config["clkfb_div"],
            p_CLKI_DIV      = config["clki_div"]
        )
        self.comb += self.locked.eq(locked & ~self.reset)
        for n, clkout in sorted(self.clkouts.items()):
            div    = config[f"clko{n}_div"]
            phase  = round(clkout.phase*div/45)
            self.params[f"p_CLKO{n_to_l[n]}_ENABLE"] = "ENABLED"
            self.params[f"p_CLKO{n_to_l[n]}_DIV"]    = div
            self.params[f"p_CLKO{n_to_l[n]}_FPHASE"] = phase & 7
            self.params[f"p_CLKO{n_to_l[n]}_CPHASE"] = (phase >> 3) + (div - 1)
            self.params[f"o_CLKO{n_to_l[n]}"]        = clkout.clk
            if clkout.freq > 0:  # i.e. not a feedback-only clock
                self.params["attr"].append((f"FREQUENCY_PIN_CLKO{n_to_l[n]}", str(clkout.freq/1e6)))
        if self.bel:
            self.params["attr"].append(("BEL", self.bel))
        self.specials += Instance("EHXPLLL", name=self.name or "", **self.params)

# Lattice / ECP5 Dynamic Delay ---------------------------------------------------------------------

class ECP5DynamicDelay(LiteXModule):
    tap_delay = 25e-12
    ntaps     = 128

    def __init__(self, i=None, o=None, taps=None):
        self.i    = Signal() if i is None else i
        self.o    = Signal() if o is None else o
        self.taps = Signal(max=self.ntaps) if taps is None else taps

        # # #

        rst       = Signal()
        move      = Signal()
        done      = Signal()
        change    = Signal()
        curr_taps = Signal(max=self.ntaps)

        # DELAYF Instance.
        self.specials += Instance("DELAYF",
            p_DEL_MODE  = "USER_DEFINED",
            p_DEL_VALUE = self.taps.reset,
            i_A         = self.i,
            o_Z         = self.o,
            i_LOADN     = ~(ResetSignal() | rst),
            i_MOVE      = move,
            i_DIRECTION = 0,
            o_CFLAG     = Signal()
        )

        # FSM.
        self.comb += done.eq(  self.taps == curr_taps)
        self.comb += change.eq(self.taps != curr_taps)
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(change,
                NextState("DELAYF-RST")
            )
        )
        fsm.act("DELAYF-RST",
            rst.eq(1),
            NextValue(move,      0),
            NextValue(curr_taps, 0),
            NextState("DELAYF-MOVE")
        )
        fsm.act("DELAYF-MOVE",
             If(done,
                NextValue(move, 0),
                NextState("IDLE")
            ).Else(
                NextValue(move, ~move),
                If(move,
                    NextValue(curr_taps, curr_taps + 1)
                )
            )
        )
