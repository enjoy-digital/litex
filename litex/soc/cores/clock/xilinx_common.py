#
# This file is part of LiteX.
#
# Copyright (c) 2018-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2026 edecoux <emilien.decoux@edu.univ-fcomte.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

from litex.soc.interconnect.csr import *

from litex.soc.cores.clock.common import *

# Xilinx / Generic ---------------------------------------------------------------------------------

class XilinxClocking(LiteXModule):

    def __init__(self, vco_margin=0):
        check_margin(vco_margin, "VCO margin")
        self.clkfbout_mult_frange = (2,  64+1)
        self.clkout_divide_range  = (1, 128+1)
        self.vco_margin = vco_margin
        self.reset      = Signal()
        self.power_down = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}

    def register_clkin(self, clkin, freq):
        check_freq_range(freq, self.clkin_freq_range, "Input clock frequency")
        self.clkin = connect_clkin(self, clkin, differential=True)
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def _check_clkout_buf(self, buf, ce):
        if buf is None:
            return None
        buf = buf.lower()
        if buf in ["bufgce", "bufgctrl"] and ce is None:
            raise ValueError("{} requires user to provide a clock enable ce Signal".format(buf.upper()))
        if buf not in ["bufg", "bufr", "bufh", "bufgce", "bufgctrl", "bufio"]:
            raise ValueError("Unsupported clock buffer: {}".format(buf))
        return buf

    def _insert_clkout_buf(self, clkout, clkout_buf, buf, ce=None):
        if buf == "bufg":
            self.specials += Instance("BUFG", i_I=clkout, o_O=clkout_buf)
        elif buf == "bufr":
            self.specials += Instance("BUFR", i_I=clkout, o_O=clkout_buf)
        elif buf == "bufh":
            self.specials += Instance("BUFH", i_I=clkout, o_O=clkout_buf)
        elif buf == "bufgce":
            self.specials += Instance("BUFGCE", i_I=clkout, o_O=clkout_buf, i_CE=ce)
        elif buf == "bufgctrl":
            self.specials += Instance("BUFGCTRL",
                p_INIT_OUT = 0,
                p_PRESELECT_I0 = "FALSE",
                p_PRESELECT_I1 = "FALSE",
                i_I0      = clkout,
                i_I1      = 0,
                i_CE0     = 1,
                i_CE1     = 1,
                i_IGNORE0 = 0,
                i_IGNORE1 = 0,
                i_S0      = ce,
                i_S1      = ~ce,
                o_O       = clkout_buf,
            )
        elif buf == "bufio":
            self.specials += Instance("BUFIO", i_I=clkout, o_O=clkout_buf)

    def _check_gated_clkout_cds(self, cd, gated_clkouts):
        clk  = getattr(cd, "clk", None)
        name = getattr(cd, "name", None) or getattr(clk, "name_override", None)
        seen = [(cd, clk, name)]
        for gated_cd in gated_clkouts:
            gated_clk  = getattr(gated_cd, "clk", None)
            gated_name = getattr(gated_cd, "name", None) or getattr(gated_clk, "name_override", None)
            for other_cd, other_clk, other_name in seen:
                if (gated_cd is other_cd or
                    (gated_clk is not None and gated_clk is other_clk) or
                    (gated_name is not None and gated_name == other_name)):
                    raise ValueError(
                        "Clock domain {} is already driven by this clocking instance.".format(
                            gated_name or "<unnamed>"
                        )
                    )
            seen.append((gated_cd, gated_clk, gated_name))
            check_clkout_cd_unused(self, gated_cd)

    def create_clkout(self, cd, freq, phase=0, buf="bufg", margin=1e-2, with_reset=True, reset_buf=None, ce=None,
        gated_clkouts=None):
        check_freq_positive(freq, "Output clock frequency")
        check_margin(margin)
        check_clkout_cd_unused(self, cd)
        check_clkout_count(self.nclkouts, self.nclkouts_max)
        if with_reset and reset_buf not in [None, "bufg"]:
            raise ValueError("Unsupported reset clock buffer: {}".format(reset_buf))
        buf = self._check_clkout_buf(buf, ce)
        if gated_clkouts is None:
            gated_clkouts = {}
        if not hasattr(gated_clkouts, "items"):
            raise ValueError("gated_clkouts must be a dict of ClockDomain: ce Signal entries.")
        self._check_gated_clkout_cds(cd, gated_clkouts)
        for gated_cd, gated_ce in gated_clkouts.items():
            self._check_clkout_buf("bufgctrl", gated_ce)
        register_clkout_cd(self, cd)
        clkout = Signal()
        self.clkouts[self.nclkouts] = ClkOut(clkout, freq, phase, margin)
        if with_reset:
            cd.rst_buf = reset_buf # FIXME: Improve.
            self.specials += AsyncResetSynchronizer(cd, ~self.locked)
        if buf is None:
            self.comb += cd.clk.eq(clkout)
        else:
            clkout_buf = Signal()
            self.comb += cd.clk.eq(clkout_buf)
            self._insert_clkout_buf(clkout, clkout_buf, buf, ce)
        for gated_cd, gated_ce in gated_clkouts.items():
            register_clkout_cd(self, gated_cd)
            if with_reset:
                gated_cd.rst_buf = reset_buf # FIXME: Improve.
                self.specials += AsyncResetSynchronizer(gated_cd, ~self.locked)
            gated_clkout_buf = Signal()
            self.comb += gated_cd.clk.eq(gated_clkout_buf)
            self._insert_clkout_buf(clkout, gated_clkout_buf, "bufgctrl", gated_ce)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        check_clkin_registered(hasattr(self, "clkin"))
        check_clkouts(self.nclkouts)
        best_config = None
        best_score  = None
        for divclk_divide in range(*self.divclk_divide_range):
            for clkfbout_mult in reversed(list(clkdiv_range(*self.clkfbout_mult_frange))): # Reverse to use highest VCO frequency.
                all_valid = True
                errors    = []
                config    = {"divclk_divide": divclk_divide}
                vco_freq  = self.clkin_freq*clkfbout_mult/divclk_divide
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if (vco_freq >= vco_freq_min*(1 + self.vco_margin) and
                    vco_freq <= vco_freq_max*(1 - self.vco_margin)):
                    for n, clkout in sorted(self.clkouts.items()):
                        d_ranges = [self.clkout_divide_range]
                        if getattr(self, "clkout{}_divide_range".format(n), None) is not None:
                            d_ranges += [getattr(self, "clkout{}_divide_range".format(n))]
                        best_clkout = clkout_best_divider(
                            clkout.freq,
                            clkout.margin,
                            clkdiv_candidates(d_ranges, ideal=vco_freq/clkout.freq),
                            lambda d: vco_freq/d
                        )
                        if best_clkout is None:
                            all_valid = False
                            break
                        error, clk_freq, d = best_clkout
                        errors.append(error)
                        config["clkout{}_freq".format(n)]   = clk_freq
                        config["clkout{}_divide".format(n)] = d
                        config["clkout{}_phase".format(n)]  = clkout.phase
                else:
                    all_valid = False
                if all_valid:
                    config["vco"]           = vco_freq
                    config["clkfbout_mult"] = clkfbout_mult
                    best_config, best_score = update_best_config(best_config, best_score, config, errors, vco_freq)
        if best_config is not None:
            compute_config_log(self.logger, best_config)
            return best_config
        raise pll_config_error(self.clkin_freq, self.clkouts)

    def expose_drp(self):
        self.drp_reset  = CSR()
        self.drp_locked = CSRStatus(1,                    description="DRP PLL/MMCM locked status.")
        self.drp_read   = CSR()
        self.drp_write  = CSR()
        self.drp_drdy   = CSRStatus(1,                    description="DRP transfer done.")
        self.drp_adr    = CSRStorage(7,  reset_less=True, description="DRP address.")
        self.drp_dat_w  = CSRStorage(16, reset_less=True, description="DRP write data.")
        self.drp_dat_r  = CSRStatus(16,                   description="DRP read data.")

        # # #

        den_pipe = Signal()
        dwe_pipe = Signal()

        drp_drdy = Signal()
        self.params.update(
            i_DCLK  = ClockSignal(),
            i_DWE   = dwe_pipe,
            i_DEN   = den_pipe,
            o_DRDY  = drp_drdy,
            i_DADDR = self.drp_adr.storage,
            i_DI    = self.drp_dat_w.storage,
            o_DO    = self.drp_dat_r.status
        )
        self.sync += [
            den_pipe.eq(self.drp_read.wr_stb | self.drp_write.wr_stb),
            dwe_pipe.eq(self.drp_write.wr_stb),
            If(self.drp_read.wr_stb | self.drp_write.wr_stb,
                self.drp_drdy.status.eq(0)
            ).Elif(drp_drdy,
                self.drp_drdy.status.eq(1)
            )
        ]
        self.comb += self.drp_locked.status.eq(self.locked)
        self.logger.info("Exposing Dynamic Reconfiguration Port (DRP) interface.")

    def expose_dps(self, clk_domain="sys", with_csr=True):
        if with_csr and clk_domain != "sys":
            raise ValueError("CSR-backed DPS must use the sys clock domain.")

        self.psen     = Signal() # i.
        self.psincdec = Signal() # i.
        self.psdone   = Signal() # o.

        self.params.update(
            i_PSCLK    = ClockSignal(clk_domain),
            i_PSEN     = self.psen,
            i_PSINCDEC = self.psincdec,
            o_PSDONE   = self.psdone
        )

        if with_csr:
            self.dps_psen     = CSRStorage(description="DPS phase-shift enable.")
            self.dps_psincdec = CSRStorage(description="DPS phase-shift direction.")
            self.dps_psdone   = CSRStatus(description="DPS phase-shift done.")
            self.dps_fsm = dps_fsm = FSM(reset_state="IDLE")
            dps_fsm.act("IDLE",
                If(self.dps_psen.storage,
                    self.psen.eq(1),
                    NextState("WAIT")
                )
            )
            dps_fsm.act("WAIT",
                If(self.psdone,
                    NextState("IDLE")
                )
            )
            self.comb += [
                self.psincdec.eq(self.dps_psincdec.storage),
                self.dps_psdone.status.eq(self.psdone),
            ]

        self.logger.info("Exposing Dynamic Phase Shift (DPS) interface.")

    def add_reset_delay(self, cycles):
        for i in range(cycles):
            reset = Signal()
            self.specials += Instance("FDCE", i_C=self.clkin, i_CE=1, i_CLR=0, i_D=self.reset, o_Q=reset)
            self.reset = reset

    def do_finalize(self):
        check_clkin_registered(hasattr(self, "clkin"))
        self.add_reset_delay(cycles=8) # Prevents interlock when reset driven from sys_clk.
