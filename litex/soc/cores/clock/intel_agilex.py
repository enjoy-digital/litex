#
# This file is part of LiteX.
#
# Copyright (c) 2025 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
#
# SPDX-License-Identifier: BSD-2-Clause

# See.
# https://www.intel.com/content/www/us/en/docs/programmable/813918/current/i-o-pll-specifications.html
# https://www.intel.com/content/www/us/en/docs/programmable/772350/24-3/i-o-pll-parameterizable-macro-ipm-iopll.html

from migen import *

from litex.gen import *

from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.intel_common import *

# Altera Agilex -----------------------------------------------------------------------------------

class AgilexPLL(IntelClocking):
    nclkouts_max          = 7
    n_div_range           = (1, 110+1)
    m_div_range           = (4, 160+1)
    c_div_range           = (1, 510+1)
    clkin_pfd_freq_range  = (10e6, 325e6)

    def __init__(self, platform, speedgrade="-6S"):
        self.logger = logging.getLogger("AgilexPLL")
        self.platform = platform
        self.clkin_name = None
        self.logger.info("Creating AgilexPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        IntelClocking.__init__(self)

        self.clko = Signal(self.nclkouts_max)

    def register_clkin(self, clkin, freq):
        if isinstance(clkin, Signal):
            self.clkin_name = clkin.name_override
        elif isinstance(clkin, ClockSignal):
            self.clkin_name = f"{clkin.cd}_clk"
        else:
            raise ValueError
        super().register_clkin(clkin, freq)

    def create_clkout(self, cd, freq, phase=0, margin=1e-2, with_reset=True):
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, phase, margin, cd.clk.name_override)
        if with_reset:
            self.specials += AsyncResetSynchronizer(cd, ~self.locked)
        if not hasattr(cd.clk, "keep"):
            cd.clk.attr.add("keep")
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        valid_configs = []

        # Calculate N divider range based on PFD frequency constraints.
        min_n = math.ceil(self.clkin_freq / self.clkin_pfd_freq_range[1])
        max_n = math.floor(self.clkin_freq / self.clkin_pfd_freq_range[0])
        min_n = max(min_n, self.n_div_range[0])
        max_n = min(max_n + 1, self.n_div_range[1])

        if min_n > max_n:
            raise ValueError("No valid N divider found for PFD frequency constraints")

        # Loop over n possible values.
        for n_factor in range(min_n, max_n):
            pfd_freq = self.clkin_freq / n_factor

            # Calculate M multiplier range based on VCO frequency constraints.
            min_m = math.ceil(self.vco_freq_range[0] / pfd_freq)
            max_m = math.floor(self.vco_freq_range[1] / pfd_freq)
            min_m = max(min_m, self.m_div_range[0])
            max_m = min(max_m+1, self.m_div_range[1])

            # Test M values:
            for m in range(min_m, max_m):
                vco_freq          = pfd_freq * m
                vco_period_ps     = 1e12 / vco_freq
                vco_phase_step_ps = vco_period_ps / 8

                # Check if VCO frequency is within range.
                if not (self.vco_freq_range[0] <= vco_freq <= self.vco_freq_range[1]):
                    continue

                # Prepare config.
                config = {
                    'n':        n_factor,
                    'm':        m,
                    'pfd_freq': int(pfd_freq),
                    'vco_freq': int(vco_freq),
                }

                # Try to find valid C dividers for all outputs.
                c_dividers        = {}
                c_phase_ps        = {}
                c_phase_shifts    = {}
                config_valid      = True
                total_error       = 0.0
                max_error         = 0.0

                for i in range(len(self.clkouts)):
                    (_, target_freq, phase, margin, name) = self.clkouts[i]
                    # Calculate ideal C divider.
                    ideal_c = vco_freq / target_freq

                    # Find the best integer C divider within constraints.
                    best_c           = None
                    best_error       = float('inf')
                    best_actual_freq = 0

                    # Check nearby integer values
                    ideal_c_i = int(ideal_c)
                    loop_c    = {
                        True:  [ideal_c_i],                              # exact frequency
                        False: [math.floor(ideal_c), math.ceil(ideal_c)] # approx frequency
                    }[ideal_c_i == ideal_c]

                    for test_c in loop_c:
                        if test_c < self.c_div_range[0] or test_c >= self.c_div_range[1]:
                            continue

                        actual_freq = vco_freq / test_c

                        # Check if output frequency is within range.
                        if not (self.clko_freq_range[0] <= actual_freq <= self.clko_freq_range[1]):
                            continue

                        error = abs(actual_freq - target_freq)
                        if error < best_error:
                            best_error       = error
                            best_c           = test_c
                            best_actual_freq = actual_freq

                    # Check if we found a valid C divider within margin.
                    if best_c is None or best_error > margin: # FIXME: check margin compare.
                        config_valid = False
                        break

                    error_pct    = best_error / target_freq
                    total_error += error_pct
                    max_error    = max(max_error, error_pct)

                    # Phase shift
                    clk_freq                            = vco_freq / best_c
                    clk_phase_step_ps                   = (1e12 / clk_freq) / 360
                    clk_phase_ps                        = clk_phase_step_ps * phase
                    clk_phase_shifts                    = clk_phase_ps / vco_phase_step_ps
                    # Update config
                    config[f"clk{i}_freq"]              = clk_freq
                    config[f"clk{i}_divide"]            = best_c
                    config[f"clk{i}_phase_ps"]          = round(clk_phase_ps)     # NB: need to use round() not int() to get proper rounding
                    config[f"clk{i}_phase_shifts"]      = round(clk_phase_shifts) # NB: need to use round() not int() to get proper rounding
                    config[f"clk{i}_dutycycle_den"]     = 2 * best_c
                    config[f"clk{i}_dutycycle_num"]     = best_c
                    config[f"clk{i}_dutycycle_percent"] = 50

                if config_valid:
                    # FIXME: check if this config already exists.
                    config["total_error"] = total_error
                    config["max_error"]   = max_error
                    valid_configs.append(config)

        if not valid_configs:
            raise ValueError("No valid PLL configuration found")

        # Sort by VCO frequency (highest first), then by total error (lowest first).
        valid_configs.sort(key=lambda x: (-x['vco_freq'], x['total_error']))

        best_config = valid_configs[0]

        # Pad remaining entries with the first divider value (matching original code behavior).
        if len(self.clkouts) < self.nclkouts_max:
            def_dt_den = 2 * (self.c_div_range[1] - 1) * 2
            for i in range(len(self.clkouts), self.nclkouts_max):
                best_config[f"clk{i}_freq"]              = {True: 0, False: best_config["vco_freq"]}[i == 1]
                best_config[f"clk{i}_divide"]            = {True: self.c_div_range[1] - 1, False: 1}[i == 1]
                best_config[f"clk{i}_phase_ps"]          = 0
                best_config[f"clk{i}_phase_shifts"]      = 0
                best_config[f"clk{i}_dutycycle_den"]     = {True: def_dt_den, False: 4}[i == 1]
                best_config[f"clk{i}_dutycycle_num"]     = {True: self.c_div_range[1] - 1, False: 2}[i == 1]
                best_config[f"clk{i}_dutycycle_percent"] = 50

        compute_config_log(self.logger, best_config)

        return best_config

    def do_finalize(self):
        config = self.compute_config()

        # Parameters
        self.params.update(
            p_bandwidth_mode              = "BANDWIDTH_MODE_AUTO",
            p_base_address                = Constant(0, 11),
            p_cascade_mode                = "CASCADE_MODE_STANDALONE",
            p_clk_switch_auto_en          = "FALSE",
            p_clk_switch_manual_en        = "FALSE",
            p_compensation_clk_source     = "COMPENSATION_CLK_SOURCE_UNUSED",
            p_compensation_mode           = "COMPENSATION_MODE_DIRECT",
            p_fb_clk_delay                = 0,
            p_fb_clk_fractional_div_den   = 1,
            p_fb_clk_fractional_div_num   = 1,
            p_fb_clk_fractional_div_value = 1,
            p_fb_clk_m_div                = config["m"],
            p_out_clk_cascading_source    = "OUT_CLK_CASCADING_SOURCE_UNUSED",
            p_out_clk_external_0_source   = "OUT_CLK_EXTERNAL_0_SOURCE_UNUSED",
            p_out_clk_external_1_source   = "OUT_CLK_EXTERNAL_1_SOURCE_UNUSED",
            p_out_clk_periph_0_delay      = 0,
            p_out_clk_periph_0_en         = "TRUE",
            p_out_clk_periph_1_delay      = 0,
            p_out_clk_periph_1_en         = "TRUE",
            p_pfd_clk_freq                = Constant(config["pfd_freq"], 32),
            p_protocol_mode               = "PROTOCOL_MODE_BASIC",
            p_ref_clk_0_freq              = Constant(self.clkin_freq, 32),
            p_ref_clk_1_freq              = Constant(0, 32),
            p_ref_clk_delay               = 0,
            p_ref_clk_n_div               = config["n"],
            p_self_reset_en               = "FALSE",
            p_set_dutycycle               = "SET_DUTYCYCLE_FRACTION",
            p_set_fractional              = "SET_FRACTIONAL_FRACTION",
            p_set_freq                    = "SET_FREQ_DIVISION_VERIFY",
            p_set_phase                   = "SET_PHASE_NUM_SHIFTS_VERIFY",
            p_vco_clk_freq                = Constant(config["vco_freq"], 36),
        )

        # Output Clocks configuration.
        for i in range(self.nclkouts_max):
            self.params[f"p_out_clk_{i}_c_div"]             = config[f"clk{i}_divide"]
            self.params[f"p_out_clk_{i}_core_en"]           = {True: "TRUE", False: "FALSE"}[i < len(self.clkouts)]
            self.params[f"p_out_clk_{i}_delay"]             = 0
            self.params[f"p_out_clk_{i}_dutycycle_den"]     = config[f"clk{i}_dutycycle_den"]
            self.params[f"p_out_clk_{i}_dutycycle_num"]     = config[f"clk{i}_dutycycle_num"]
            self.params[f"p_out_clk_{i}_dutycycle_percent"] = config[f"clk{i}_dutycycle_percent"]
            self.params[f"p_out_clk_{i}_freq"]              = Constant(config[f"clk{i}_freq"], 36)
            self.params[f"p_out_clk_{i}_phase_ps"]          = config[f"clk{i}_phase_ps"]
            self.params[f"p_out_clk_{i}_phase_shifts"]      = config[f"clk{i}_phase_shifts"]

        # Signals.
        self.params.update(
            # Clk/Reset.
            i_ref_clk0             = self.clkin,
            i_ref_clk1             = Constant(0, 1),
            i_reset                = self.reset,
            o_lock                 = self.locked,

            # Calibration Interface.
            i_cal_bus_rst_n        = Constant(0, 1),
            i_cal_bus_clk          = Constant(0, 1),
            i_cal_bus_write        = Constant(0, 1),
            i_cal_bus_read         = Constant(0, 1),
            i_cal_bus_address      = Constant(0, 22),
            i_cal_bus_writedata    = Constant(0, 32),
            o_cal_bus_readdata     = Open(32),
            i_permit_cal           = Constant(1, 1),

            # Feedback Clocks.
            i_fb_clk_in            = Constant(0, 1),
            i_fb_clk_in_lvds       = Constant(0, 1),
            o_fb_clk_out           = Open(),

            # Output Clocks.
            o_out_clk              = self.clko,
            o_out_clk_cascade      = Open(),
            o_out_clk_external0    = Open(),
            o_out_clk_external1    = Open(),
            o_out_clk_periph0      = Open(),
            o_out_clk_periph1      = Open(),

            # Ref Clks Signals.
            o_ref_clk_active       = Open(),
            o_ref_clk_bad          = Open(2),
            i_ref_clk_switch_n     = Constant(1),

            # VCO.
            o_vco_clk              = Open(),
            o_vco_clk_periph       = Open(),
        )

        for c in range(self.nclkouts):
            self.comb += self.clkouts[c][0].eq(self.clko[c])

        inst = self.clkin_name+"_pll"
        self.specials += Instance("tennm_ph2_iopll", name=inst, **self.params)

        ## Add timing constraints
        # First, generate the internal PLL reference clock
        sdc = self.platform.toolchain.clock_constraints
        sdc.append("# ------------------------ #")
        sdc.append("# -                      - #")
        sdc.append("# ---REFERENCE CLOCK(s)--- #")
        sdc.append("# -                      - #")
        sdc.append("# ------------------------ #")

        refname = f"{inst}|ref_clk0"
        sdc.append(f"create_generated_clock -add -name {refname} -divide_by 1 -multiply_by 1 \\")
        sdc.append(f"    -master {self.clkin_name} -source {self.clkin_name} [get_nodes {{{refname}}}]")

        sdc.append("# ------------------------ #")
        sdc.append("# -                      - #")
        sdc.append("# --- N/M COUNTERS(s)  --- #")
        sdc.append("# -                      - #")
        sdc.append("# ------------------------ #")

        # N counter
        nname   = f"{inst}_n_cnt_clk"
        ntarget = f"{inst}|~ncntr_reg"
        ndiv    = config["n"]
        sdc.append(f"create_generated_clock -add -name {nname} -divide_by {ndiv} -multiply_by 1 \\")
        sdc.append(f"    -master {refname} -source {refname} [get_nodes {{{ntarget}}}]")
        # M counter
        mname   = f"{inst}_m_cnt_clk"
        mtarget = f"{inst}|~mcntr_reg"
        mmaster = nname if ndiv > 1 else refname
        msource = ntarget if ndiv > 1 else refname
        sdc.append(f"create_generated_clock -add -name {mname} -divide_by 1 -multiply_by 1 \\")
        sdc.append(f"    -master {mmaster} -source {msource} [get_nodes {{{mtarget}}}]")

        sdc.append("# ------------------------- #")
        sdc.append("# -                       - #")
        sdc.append("# --- OUTPUT PLL CLOCKS --- #")
        sdc.append("# -                       - #")
        sdc.append("# ------------------------- #")
        for i in range(len(self.clkouts)):
            (_, target_freq, phase, margin, name) = self.clkouts[i]
            if not name:
                name = f"{inst}_outclk{i}"
            master = nname if ndiv > 1 else refname
            source = ntarget if ndiv > 1 else refname
            target = f"{inst}|out_clk[{i}]"
            div    = config[f"clk{i}_divide"]
            mult   = config["m"]
            sdc.append(f"create_generated_clock -add -name {name} \\")
            sdc.append(f"    -duty_cycle 50 -divide_by {div} -multiply_by {mult} -phase {phase} \\")
            sdc.append(f"    -master {master} -source {source} [get_nodes {{{target}}}]")

# Altera Agilex3 -----------------------------------------------------------------------------------

class Agilex3PLL(AgilexPLL):
    def __init__(self, platform, speedgrade=None):
        if speedgrade is None:
            # Speedgrade is the last two characters of the device
            speedgrade = "-" + platform.device[-2:]
        self.clkin_freq_range = {
            "-6S" : (10e6,  900e6),
            "-7S" : (10e6,  625e6),
        }[speedgrade]

        self.vco_freq_range = {
            "-6S" : (600e6, 3200e6),
            "-7S" : (600e6, 2400e6),
        }[speedgrade]

        self.clko_freq_range = {
            "-6S" : (0e6, 1000e6),
            "-7S" : (0e6,  780e6),
        }[speedgrade]

        AgilexPLL.__init__(self, platform, speedgrade)

# Altera Agilex5 -----------------------------------------------------------------------------------

class Agilex5PLL(AgilexPLL):
    def __init__(self, platform, speedgrade="-6S"):
        self.clkin_freq_range = {
            "-1V" : (10e6, 1100e6),
            "-2E" : (10e6,  900e6),
            "-2V" : (10e6,  900e6),
            "-3V" : (10e6,  625e6),
            "-4S" : (10e6, 1100e6),
            "-5S" : (10e6,  900e6),
            "-6S" : (10e6,  625e6),
            "-6X" : (10e6,  625e6),
        }[speedgrade]

        self.vco_freq_range = {
            "-1V" : (600e6, 3200e6),
            "-2E" : (600e6, 3200e6),
            "-2V" : (600e6, 3200e6),
            "-3V" : (600e6, 2400e6),
            "-4S" : (600e6, 3200e6),
            "-5S" : (600e6, 3200e6),
            "-6S" : (600e6, 2400e6),
            "-6X" : (600e6, 2400e6),
        }[speedgrade]

        self.clko_freq_range = {
            "-1V" : (0e6, 1100e6),
            "-2V" : (0e6, 1000e6),
            "-2E" : (0e6, 1000e6),
            "-3V" : (0e6,  780e6),
            "-4S" : (0e6, 1100e6),
            "-5S" : (0e6, 1000e6),
            "-6S" : (0e6,  780e6),
            "-6X" : (0e6,  780e6),
        }[speedgrade]

        AgilexPLL.__init__(self, platform, speedgrade)

# Altera Agilex7 -----------------------------------------------------------------------------------

class Agilex7PLL(AgilexPLL):
    def __init__(self, platform, speedgrade="-6S"):
        self.clkin_freq_range = {
            "-1V" : (10e6,  1100e6),
            "-2V" : (10e6,  1000e6),
            "-3V" : (10e6,  780e6),
            "-3E" : (10e6,  780e6),
        }[speedgrade]

        self.vco_freq_range = {
            "-1V" : (600e6, 3200e6),
            "-2V" : (600e6, 3200e6),
            "-3V" : (600e6, 2400e6),
            "-3E" : (600e6, 2400e6),
        }[speedgrade]

        self.clko_freq_range = {
            "-1V" : (0e6, 1100e6),
            "-2V" : (0e6, 1000e6),
            "-3V" : (0e6,  780e6),
            "-3E" : (0e6,  780e6),
        }[speedgrade]

        AgilexPLL.__init__(self, platform, speedgrade)
