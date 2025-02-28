#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex.gen import *

from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.xilinx_common import *
from typing import Dict, Any
import math

# Xilinx / Ultrascale Plus PLL ---------------------------------------------------------------------

# TODO:
# - use Ultrascale Plus primitives instead of 7-Series' ones. (Vivado recognize and convert them).

class USPPLL(XilinxClocking):
    nclkouts_max = 6

    def __init__(self, speedgrade=-1):
        self.logger = logging.getLogger("USPPLL")
        self.logger.info("Creating USPPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 56+1)
        self.clkin_freq_range = {
            -1: (70e6,  800e6),
            -2: (70e6,  933e6),
            -3: (70e6, 1066e6),
        }[speedgrade]
        self.vco_freq_range = {
            -1: (750e6, 1500e6),
            -2: (750e6, 1500e6),
            -3: (750e6, 1500e6),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        pll_fb = Signal()
        self.params.update(
            # Global.
            p_STARTUP_WAIT = "FALSE",
            i_RST          = self.reset,
            i_PWRDWN       = self.power_down,
            o_LOCKED       = self.locked,

            # VCO.
            p_REF_JITTER1   = 0.01,
            p_CLKIN1_PERIOD = 1e9/self.clkin_freq,
            p_CLKFBOUT_MULT = config["clkfbout_mult"],
            p_DIVCLK_DIVIDE = config["divclk_divide"],
            i_CLKIN1        = self.clkin,
            i_CLKFBIN       = pll_fb,
            o_CLKFBOUT      = pll_fb,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            self.params["p_CLKOUT{}_DIVIDE".format(n)] = config["clkout{}_divide".format(n)]
            self.params["p_CLKOUT{}_PHASE".format(n)]  = config["clkout{}_phase".format(n)]
            self.params["o_CLKOUT{}".format(n)]        = clk
        self.specials += Instance("PLLE2_ADV", **self.params)

# Xilinx / Ultrascale Plus MMCM --------------------------------------------------------------------

class USPMMCM(XilinxClocking):
    nclkouts_max = 7

    def __init__(self, speedgrade=-1):
        self.logger = logging.getLogger("USPMMCM")
        self.logger.info("Creating USPMMCM, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 106+1)
        self.clkin_freq_range = {
            -1: (10e6,  800e6),
            -2: (10e6,  933e6),
            -3: (10e6, 1066e6),
        }[speedgrade]
        self.vco_freq_range = {
            -1: (800e6, 1600e6),
            -2: (800e6, 1600e6),
            -3: (800e6, 1600e6),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        mmcm_fb = Signal()
        self.params.update(
            # Global.
            p_BANDWIDTH = "OPTIMIZED",
            i_RST       = self.reset,
            i_PWRDWN    = self.power_down,
            o_LOCKED    = self.locked,

            # VCO.
            p_REF_JITTER1     = 0.01,
            p_CLKIN1_PERIOD   = 1e9/self.clkin_freq,
            p_CLKFBOUT_MULT_F = config["clkfbout_mult"],
            p_DIVCLK_DIVIDE   = config["divclk_divide"],
            i_CLKIN1          = self.clkin,
            i_CLKFBIN         = mmcm_fb,
            o_CLKFBOUT        = mmcm_fb,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            if n == 0:
                self.params["p_CLKOUT{}_DIVIDE_F".format(n)] = config["clkout{}_divide".format(n)]
            else:
                self.params["p_CLKOUT{}_DIVIDE".format(n)] = config["clkout{}_divide".format(n)]
            self.params["p_CLKOUT{}_PHASE".format(n)] = config["clkout{}_phase".format(n)]
            self.params["o_CLKOUT{}".format(n)]       = clk
        self.specials += Instance("MMCME4_ADV", **self.params)

    def compute_config(self) -> Dict[str, Any]:
        """
        Computes the MMCM configuration based on input parameters.

        Returns:
            Dict[str, Any]: A dictionary containing MMCM configuration parameters.

        Raises:
            ValueError: If no valid MMCM configuration is found.
        """
        vco_min_margin = self.vco_freq_range[0] * (1 + self.vco_margin)
        vco_max_margin = self.vco_freq_range[1] * (1 - self.vco_margin)
        # ref: https://docs.amd.com/r/en-US/ug572-ultrascale-clocking/MMCM-Attributes
        # CLKFBOUT_MULT_F: 2.0 to 128.0 with step 0.125
        clkfbout_mult_f_values = [x / 8 for x in range(16, 1025)]

        for divclk_divide in range(*self.divclk_divide_range):
            for clkfbout_mult in reversed(clkfbout_mult_f_values):
                vco_freq = self.clkin_freq * clkfbout_mult / divclk_divide
                if not (vco_min_margin <= vco_freq <= vco_max_margin):
                    continue # vco_freq out of range

                config: Dict[str, Any] = {
                    "divclk_divide": divclk_divide,
                    "clkfbout_mult": clkfbout_mult,
                    "vco": vco_freq
                }
                all_valid = True
                for n, (clk, f, p, m) in sorted(self.clkouts.items()):
                    valid = False

                    dividers = list(clkdiv_range(*self.clkout_divide_range))
                    # Add specific range dividers if they exist
                    specific_div_range = getattr(self, f"clkout{n}_divide_range", None)
                    if specific_div_range:
                        dividers.extend(clkdiv_range(*specific_div_range))

                    # For clkout0, CLKOUT[0]_DIVIDE_F also has range 2.0 to 128.0 with step 0.125
                    if n == 0:
                        dividers = [x / 8 for x in range(16, 1025)]

                    for d in dividers:
                        clk_freq = vco_freq / d
                        if not math.isclose(clk_freq, f, rel_tol=m):
                        # if abs(clk_freq - f) <= f * m:
                            continue

                        config[f"clkout{n}_freq"] = clk_freq
                        config[f"clkout{n}_divide"] = d
                        config[f"clkout{n}_phase"] = p
                        valid = True
                        break # Valid divider found

                    if not valid:
                        all_valid = False
                        break # Exit early if any clock output is invalid

                if all_valid:
                    compute_config_log(self.logger, config)
                    return config

        raise ValueError("No MMCM config found")

# Xilinx / Ultrascale Plus IDELAY CTRL -------------------------------------------------------------

class USPIDELAYCTRL(LiteXModule):
    def __init__(self, cd_ref, cd_sys, reset_cycles=64, ready_cycles=64):
        self.cd_ic = ClockDomain()
        ic_reset_counter = Signal(max=reset_cycles, reset=reset_cycles-1)
        ic_reset         = Signal(reset=1)
        cd_ref_sync      = getattr(self.sync, cd_ref.name)
        cd_ref_sync += [
            If(ic_reset_counter != 0,
                ic_reset_counter.eq(ic_reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        ]
        ic_ready_counter = Signal(max=ready_cycles, reset=ready_cycles-1)
        ic_ready         = Signal()
        self.comb += self.cd_ic.clk.eq(cd_sys.clk)
        self.sync.ic += [
            cd_sys.rst.eq(1),
            If(ic_ready,
                If(ic_ready_counter != 0,
                    ic_ready_counter.eq(ic_ready_counter - 1)
                ).Else(
                    cd_sys.rst.eq(0)
                )
            )
        ]
        self.specials += [
            Instance("IDELAYCTRL",
                p_SIM_DEVICE = "ULTRASCALE",
                i_REFCLK     = cd_ref.clk,
                i_RST        = ic_reset,
                o_RDY        = ic_ready),
            AsyncResetSynchronizer(self.cd_ic, ic_reset)
        ]
