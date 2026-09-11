#
# This file is part of LiteX.
#
# Copyright (c) 2019 Michael Betz <michibetz@gmail.com>
# Copyright (c) 2019-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.xilinx_common import *

# Xilinx / Spartan6 PLL ----------------------------------------------------------------------------

class S6PLL(XilinxClocking):
    nclkouts_max = 6
    clkin_freq_range = (19e6, 540e6)

    def __init__(self, speedgrade=-1, name=None):
        self.logger = logging.getLogger("S6PLL")
        self.logger.info("Creating S6PLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.name = name
        self.divclk_divide_range = (1, 52 + 1)
        self.vco_freq_range      = {
            -1: (400e6, 1000e6),
            -2: (400e6, 1000e6),
            -3: (400e6, 1080e6),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        pll_fb = Signal()
        self.params.update(
            # Global.
            p_SIM_DEVICE     = "SPARTAN6",
            p_BANDWIDTH      = "OPTIMIZED",
            p_COMPENSATION   = "INTERNAL",
            i_RST            = self.reset,
            o_LOCKED         = self.locked,

            # VCO.
            p_REF_JITTER     = .01, p_CLK_FEEDBACK="CLKFBOUT",
            p_CLKIN1_PERIOD  = 1e9/self.clkin_freq,
            p_CLKIN2_PERIOD  = 0.,
            p_CLKFBOUT_MULT  = config["clkfbout_mult"],
            p_CLKFBOUT_PHASE = 0.,
            p_DIVCLK_DIVIDE  = config["divclk_divide"],
            i_CLKINSEL       = 1,
            i_CLKIN1         = self.clkin,
            i_CLKFBIN        = pll_fb,
            o_CLKFBOUT       = pll_fb,
        )
        for n, clkout in sorted(self.clkouts.items()):
            self.params["p_CLKOUT{}_DIVIDE".format(n)]     = config["clkout{}_divide".format(n)]
            self.params["p_CLKOUT{}_PHASE".format(n)]      = float(config["clkout{}_phase".format(n)])
            self.params["p_CLKOUT{}_DUTY_CYCLE".format(n)] = 0.5
            self.params["o_CLKOUT{}".format(n)]            = clkout.clk
        self.specials += Instance("PLL_ADV", name=self.name or "", **self.params)

# Xilinx / Spartan6 DCM ----------------------------------------------------------------------------

class S6DCM(XilinxClocking):
    """ single output with f_out = f_in * {2 .. 256} / {1 .. 256} """
    nclkouts_max = 1

    def __init__(self, speedgrade=-1, name=None):
        self.logger = logging.getLogger("S6DCM")
        self.logger.info("Creating S6DCM, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.name = name
        self.clkfbout_mult_frange = (2, 256+1)
        self.clkout_divide_range  = (1, 256+1)
        self.clkin_freq_range = {
            -1: (0.5e6, 200e6),
            -2: (0.5e6, 333e6),
            -3: (0.5e6, 375e6),
        }[speedgrade]

        # DS162, Table 57: DCM_CLKGEN CLKFX output frequency limits.
        self.clkout_freq_range = {
            -1: (5e6, 200e6),
            -2: (5e6, 333e6),
            -3: (5e6, 375e6),
        }[speedgrade]

    def create_clkout(self, cd, freq, phase=0, buf="bufg", margin=1e-2, with_reset=True, reset_buf=None, ce=None):
        check_freq_range(freq, self.clkout_freq_range, "Output clock frequency")
        if phase != 0:
            raise ValueError("S6DCM does not support output phase shifts.")
        XilinxClocking.create_clkout(self, cd, freq, phase, buf, margin, with_reset, reset_buf, ce)

    def compute_config(self):
        check_clkin_registered(hasattr(self, "clkin"))
        check_clkouts(self.nclkouts)
        clkout = self.clkouts[0]
        best_config = None
        best_score  = None
        for divider in range(*self.clkout_divide_range):
            # UG382, Table 2-9: required for locking below 52MHz.
            if self.clkin_freq < 52e6 and divider >= self.clkin_freq/0.5e6:
                continue
            for multiplier in range(*self.clkfbout_mult_frange):
                clkout_freq = self.clkin_freq*multiplier/divider
                if not (self.clkout_freq_range[0] <= clkout_freq <= self.clkout_freq_range[1]):
                    continue
                error = clkout_freq_error(clkout_freq, clkout.freq)
                if error > clkout.margin:
                    continue
                config = {
                    "clkfbout_mult": multiplier,
                    "divclk_divide": 1,
                    "clkout0_freq": clkout_freq,
                    "clkout0_divide": divider,
                    "clkout0_phase": clkout.phase,
                }
                best_config, best_score = update_best_config(best_config, best_score, config, [error])
        if best_config is not None:
            compute_config_log(self.logger, best_config)
            return best_config
        raise pll_config_error(self.clkin_freq, self.clkouts)

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        clkout = sorted(self.clkouts.items())[0][1]
        self.params.update(
            p_CLKFX_MULTIPLY  = config["clkfbout_mult"],
            p_CLKFX_DIVIDE    = config["clkout0_divide"],
            p_SPREAD_SPECTRUM = "NONE",
            p_CLKIN_PERIOD    = 1e9/self.clkin_freq,
            i_CLKIN           = self.clkin,
            i_RST             = self.reset,
            i_FREEZEDCM       = 0,
            o_CLKFX           = clkout.clk,
            o_LOCKED          = self.locked,
        )
        self.specials += Instance("DCM_CLKGEN", name=self.name or "", **self.params)

    def expose_drp(self):
        self._cmd_data      = CSRStorage(10, description="DCM programming command data.")
        self._send_cmd_data = CSR()
        self._send_go       = CSR()
        self._status        = CSRStatus(4, description="DCM programming status.")

        progdata = Signal()
        progen   = Signal()
        progdone = Signal()
        locked   = Signal()

        self.params.update(
            i_PROGCLK         = ClockSignal(),
            i_PROGDATA        = progdata,
            i_PROGEN          = progen,
            o_PROGDONE        = progdone
        )

        remaining_bits = Signal(max=11)
        transmitting   = Signal()
        self.comb += transmitting.eq(remaining_bits != 0)
        sr = Signal(10)
        self.sync += [
            If(self._send_cmd_data.wr_stb,
                remaining_bits.eq(10),
                sr.eq(self._cmd_data.storage)
            ).Elif(transmitting,
                remaining_bits.eq(remaining_bits - 1),
                sr.eq(sr[1:])
            )
        ]
        self.comb += [
            progdata.eq(transmitting & sr[0]),
            progen.eq(transmitting | self._send_go.wr_stb)
        ]

        # Enforce gap between commands
        busy_counter = Signal(max=14)
        busy         = Signal()
        self.comb += busy.eq(busy_counter != 0)
        self.sync += If(self._send_cmd_data.wr_stb,
                busy_counter.eq(13)
            ).Elif(busy,
                busy_counter.eq(busy_counter - 1)
            )

        self.comb += self._status.status.eq(Cat(busy, progdone, self.locked))

        self.logger.info("Exposing DRP interface.")
