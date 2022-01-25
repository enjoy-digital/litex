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

# Xilinx / Generic ---------------------------------------------------------------------------------

class XilinxClocking(Module, AutoCSR):
    clkfbout_mult_frange = (2,  64+1)
    clkout_divide_range  = (1, 128+1)

    def __init__(self, vco_margin=0):
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
        self.clkin = Signal()
        if isinstance(clkin, (Signal, ClockSignal)):
            self.comb += self.clkin.eq(clkin)
        elif isinstance(clkin, Record):
            self.specials += DifferentialInput(clkin.p, clkin.n, self.clkin)
        else:
            raise ValueError
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, buf="bufg", margin=1e-2, with_reset=True, ce=None):
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, phase, margin)
        if with_reset:
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
            elif buf == "bufgce":
                if ce is None:
                    raise ValueError("BUFGCE requires user to provide a clock enable ce Signal")
                self.specials += Instance("BUFGCE", i_I=clkout, o_O=clkout_buf, i_CE=ce)
            elif buf == "bufio":
                self.specials += Instance("BUFIO", i_I=clkout, o_O=clkout_buf)
            else:
                raise ValueError("Unsupported clock buffer: {}".format(buf))
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        config = {}
        for divclk_divide in range(*self.divclk_divide_range):
            config["divclk_divide"] = divclk_divide
            for clkfbout_mult in reversed(range(*self.clkfbout_mult_frange)):
                all_valid = True
                vco_freq = self.clkin_freq*clkfbout_mult/divclk_divide
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if (vco_freq >= vco_freq_min*(1 + self.vco_margin) and
                    vco_freq <= vco_freq_max*(1 - self.vco_margin)):
                    for n, (clk, f, p, m) in sorted(self.clkouts.items()):
                        valid = False
                        d_ranges = [self.clkout_divide_range]
                        if getattr(self, "clkout{}_divide_range".format(n), None) is not None:
                            d_ranges += [getattr(self, "clkout{}_divide_range".format(n))]
                        for d_range in d_ranges:
                            for d in clkdiv_range(*d_range):
                                clk_freq = vco_freq/d
                                if abs(clk_freq - f) <= f*m:
                                    config["clkout{}_freq".format(n)]   = clk_freq
                                    config["clkout{}_divide".format(n)] = d
                                    config["clkout{}_phase".format(n)]  = p
                                    valid = True
                                    break
                                if valid:
                                    break
                        if not valid:
                            all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"]           = vco_freq
                    config["clkfbout_mult"] = clkfbout_mult
                    compute_config_log(self.logger, config)
                    return config
        raise ValueError("No PLL config found")

    def expose_drp(self):
        self.drp_reset  = CSR()
        self.drp_locked = CSRStatus()
        self.drp_read   = CSR()
        self.drp_write  = CSR()
        self.drp_drdy   = CSRStatus()
        self.drp_adr    = CSRStorage(7,  reset_less=True)
        self.drp_dat_w  = CSRStorage(16, reset_less=True)
        self.drp_dat_r  = CSRStatus(16)

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
            den_pipe.eq(self.drp_read.re | self.drp_write.re),
            dwe_pipe.eq(self.drp_write.re),
            If(self.drp_read.re | self.drp_write.re,
                self.drp_drdy.status.eq(0)
            ).Elif(drp_drdy,
                self.drp_drdy.status.eq(1)
            )
        ]
        self.comb += self.drp_locked.status.eq(self.locked)
        self.logger.info("Exposing DRP interface.")

    def add_reset_delay(self, cycles):
        for i in range(cycles):
            reset = Signal()
            self.specials += Instance("FDCE", i_C=self.clkin, i_CE=1, i_CLR=0, i_D=self.reset, o_Q=reset)
            self.reset = reset

    def do_finalize(self):
        assert hasattr(self, "clkin")
        self.add_reset_delay(cycles=8) # Prevents interlock when reset driven from sys_clk.
