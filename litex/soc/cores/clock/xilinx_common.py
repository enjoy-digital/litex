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

    def create_clkout(self, cd, freq, phase=0, buf="bufg", margin=1e-2, with_reset=True, reset_buf=None, ce=None):
        check_freq_positive(freq, "Output clock frequency")
        check_margin(margin)
        check_clkout_cd_unused(self, cd)
        check_clkout_count(self.nclkouts, self.nclkouts_max)
        if with_reset and reset_buf not in [None, "bufg"]:
            raise ValueError("Unsupported reset clock buffer: {}".format(reset_buf))
        if buf is not None:
            buf = buf.lower()
            if buf == "bufgce" and ce is None:
                raise ValueError("BUFGCE requires user to provide a clock enable ce Signal")
            if buf not in ["bufg", "bufr", "bufh", "bufgce", "bufio"]:
                raise ValueError("Unsupported clock buffer: {}".format(buf))
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
            if buf == "bufg":
                self.specials += Instance("BUFG", i_I=clkout, o_O=clkout_buf)
            elif buf == "bufr":
                self.specials += Instance("BUFR", i_I=clkout, o_O=clkout_buf)
            elif buf == "bufh":
                self.specials += Instance("BUFH", i_I=clkout, o_O=clkout_buf)
            elif buf == "bufgce":
                self.specials += Instance("BUFGCE", i_I=clkout, o_O=clkout_buf, i_CE=ce)
            elif buf == "bufio":
                self.specials += Instance("BUFIO", i_I=clkout, o_O=clkout_buf)
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
