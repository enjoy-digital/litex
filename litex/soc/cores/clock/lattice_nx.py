#
# This file is part of LiteX.
#
# Copyright (c) 2020 David Corrigan <davidcorrigan714@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple
import logging
import math
import pprint
from math import log, log10, exp, pi
from cmath import phase

from migen import *

from litex.soc.cores.clock.common import *

io_i2 = namedtuple('io_i2',['io', 'i2', 'IPP_CTRL', 'BW_CTL_BIAS', 'IPP_SEL'])
nx_pll_param_permutation = namedtuple("nx_pll_param_permutation",[
                                "C1","C2","C3","C4","C5","C6",
                                "IPP_CTRL","BW_CTL_BIAS","IPP_SEL","CSET","CRIPPLE","V2I_PP_RES","IPI_CMP"])


# Lattice / NX OSCA --------------------------------------------------------------------------------
# NOTE This clock has +/- 15% accuracy

class NXOSCA(Module):
    nclkouts_max = 2
    clk_hf_div_range = (0, 255)
    clk_hf_freq_range = (1.76, 450e6)
    clk_hf_freq = 450e6

    def __init__(self):
        self.logger = logging.getLogger("NXOSCA")
        self.logger.info("Creating NXOSCA.")

        self.hf_clk_out    = {}
        self.hfsdc_clk_out = {}
        self.lf_clk_out    = None
        self.params        = {}

    def create_hf_clk(self, cd, freq, margin=.05):
        """450 - 1.7 Mhz Clk"""
        (clko_freq_min, clko_freq_max) = self.clk_hf_freq_range
        assert freq >= clko_freq_min
        assert freq <= clko_freq_max
        clkout = Signal()
        self.hf_clk_out = (clkout, freq, margin)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, -1)

    def create_hfsdc_clk(self, cd, freq, margin=.05):
        """450 - 1.7 Mhz Clk. Can only be connected to the SEDC_CLK port of CONFIG_CLKRST_CORE"""
        (clko_freq_min, clko_freq_max) = self.clk_hf_freq_range
        assert freq >= clko_freq_min
        assert freq <= clko_freq_max
        clkout = Signal()
        self.hfsdc_clk_out = (clkout, freq, margin)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, -1)

    def create_lf_clk(self, cd):
        """128 kHz Clock"""
        clkout = Signal()
        self.lf_clk_out = (clkout)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, 128e3, 19e3, -1)

    def compute_divisor(self, freq, margin):
        config = {}

        for divisor in range(*self.clk_hf_div_range):
            clk_freq = self.clk_hf_freq/(divisor+1)
            if abs(clk_freq - freq) <= freq*margin:
                config["freq"]  = clk_freq
                config["div"]   = str(divisor)
                break

        if config:
            compute_config_log(self.logger, config)
            return config["div"]

        raise ValueError("Bad OSC freq.")

    def do_finalize(self):
        if self.hf_clk_out:
            divisor = self.compute_divisor(self.hf_clk_out[1], self.hf_clk_out[2])
            self.params["i_HFOUTEN"]      = 0b1
            self.params["p_HF_CLK_DIV"]   = divisor
            self.params["o_HFCLKOUT"]     = self.hf_clk_out[0]
            self.params["p_HF_OSC_EN"]    = "ENABLED"

        if self.hfsdc_clk_out:
            divisor = self.compute_divisor(self.hfsdc_clk_out[1], self.hfsdc_clk_out[2])
            self.params["i_HFSDSCEN"]        = 0b1
            self.params["p_HF_SED_SEC_DIV"]  = divisor
            self.params["o_HFSDCOUT"]        = self.hfsdc_clk_out[0]

        if self.lf_clk_out is not None:
            self.params["o_LFCLKOUT"] = self.lf_clk_out[0]
            self.params["p_LF_OUTPUT_EN"] = "ENABLED"

        self.specials += Instance("OSCA", **self.params)

# Lattice / NX PLL ---------------------------------------------------------------------------------

class NXPLL(Module):
    nclkouts_max        = 5
    clki_div_range      = ( 1, 128+1)
    clkfb_div_range     = ( 1, 128+1)
    clko_div_range      = ( 1, 128+1)
    clki_freq_range     = ( 10e6,   500e6)
    clko_freq_range     = ( 6.25e6, 800e6)
    vco_in_freq_range   = ( 10e6,   500e6)
    vco_out_freq_range  = ( 800e6,  1600e6)
    instance_num        = 0

    def __init__(self, platform = None, create_output_port_clocks=False):
        self.logger = logging.getLogger("NXPLL")
        self.logger.info("Creating NXPLL.")
        self.params     = {}
        self.reset      = Signal()
        self.locked     = Signal()
        self.params["o_LOCK"] = self.locked
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.name       = 'PLL_' + str(NXPLL.instance_num)
        NXPLL.instance_num += 1
        self.platform   = platform
        self.create_output_port_clocks = create_output_port_clocks

        self.calc_valid_io_i2()
        self.calc_tf_coefficients()

    def register_clkin(self, clkin, freq):
        (clki_freq_min, clki_freq_max) = self.clki_freq_range
        assert freq >= clki_freq_min
        assert freq <= clki_freq_max
        self.clkin = Signal()
        if isinstance(clkin, (Signal, ClockSignal)):
            self.comb += self.clkin.eq(clkin)
        else:
            raise ValueError
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, margin=1e-2):
        (clko_freq_min, clko_freq_max) = self.clko_freq_range
        assert freq >= clko_freq_min
        assert freq <= clko_freq_max
        assert self.nclkouts < self.nclkouts_max
        self.clkouts[self.nclkouts] = (cd.clk, freq, phase, margin)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        config = {}
        for clki_div in range(*self.clki_div_range):
            config["clki_div"] = clki_div
            for clkfb_div in range(*self.clkfb_div_range):
                all_valid = True
                vco_freq = self.clkin_freq/clki_div*clkfb_div
                (vco_freq_min, vco_freq_max) = self.vco_out_freq_range
                if vco_freq >= vco_freq_min and vco_freq <= vco_freq_max:
                    for n, (clk, f, p, m) in sorted(self.clkouts.items()):
                        valid = False
                        for d in range(*self.clko_div_range):
                            clk_freq = vco_freq/d
                            if abs(clk_freq - f) <= f*m:
                                config["clko{}_freq".format(n)]  = clk_freq
                                config["clko{}_div".format(n)]   = d
                                config["clko{}_phase".format(n)] = p
                                valid = True
                                break
                        if not valid:
                            all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"] = vco_freq
                    config["clkfb_div"] = clkfb_div
                    compute_config_log(self.logger, config)
                    return config
        raise ValueError("No PLL config found")

    def calculate_analog_parameters(self, clki_freq, fb_div, bw_factor = 5):
        config = {}

        params = self.calc_optimal_params(clki_freq, fb_div, 1, bw_factor)
        config["p_CSET"]            = params["CSET"]
        config["p_CRIPPLE"]         = params["CRIPPLE"]
        config["p_V2I_PP_RES"]      = params["V2I_PP_RES"]
        config["p_IPP_SEL"]         = params["IPP_SEL"]
        config["p_IPP_CTRL"]        = params["IPP_CTRL"]
        config["p_BW_CTL_BIAS"]     = params["BW_CTL_BIAS"]
        config["p_IPI_CMP"]         = params["IPI_CMP"]

        return config

    def do_finalize(self):
        config = self.compute_config()
        clkfb  = Signal()

        self.params.update(
            p_V2I_PP_ICTRL      = "0b11111", # Hard coded in all reference files
            p_IPI_CMPN          = "0b0011", # Hard coded in all reference files

            p_V2I_1V_EN         = "ENABLED", # Enabled = 1V (Default in references, but not the primitive), Disabled = 0.9V
            p_V2I_KVCO_SEL      = "60", # if (VOLTAGE == 0.9V) 85 else 60
            p_KP_VCO            = "0b00011", # if (VOLTAGE == 0.9V) 0b11001 else 0b00011

            p_PLLPD_N           = "USED",
            p_PLLRESET_ENA      = "ENABLED",
            p_REF_INTEGER_MODE  = "ENABLED", # Ref manual has a discrepency so lets always set this value just in case
            p_REF_MMD_DIG       = "1", # Divider for the input clock, ie 'M'

            i_PLLRESET          = self.reset,
            i_REFCK             = self.clkin,
            o_LOCK              = self.locked,

            # Use CLKOS5 & divider for feedback
            p_SEL_FBK           = "FBKCLK5",
            p_ENCLK_CLKOS5      = "ENABLED",
            p_DIVF              = str(config["clkfb_div"]-1), # str(Actual value - 1)
            p_DELF              = str(config["clkfb_div"]-1),
            p_CLKMUX_FB         = "CMUX_CLKOS5",
            i_FBKCK             = clkfb,
            o_CLKOS5            = clkfb,

            # Set feedback divider to 1
            p_FBK_INTEGER_MODE  = "ENABLED",
            p_FBK_MASK          = "0b00000000",
            p_FBK_MMD_DIG       = "1",
        )

        analog_params = self.calculate_analog_parameters(self.clkin_freq, config["clkfb_div"])
        self.params.update(analog_params)
        n_to_l = {0: "P", 1: "S", 2: "S2", 3:"S3", 4:"S4"}

        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            div    = config["clko{}_div".format(n)]
            phase = int((1+p/360) * div)
            letter = chr(n+65)
            self.params["p_ENCLK_CLKO{}".format(n_to_l[n])] = "ENABLED"
            self.params["p_DIV{}".format(letter)] = str(div-1)
            self.params["p_PHI{}".format(letter)] = "0"
            self.params["p_DEL{}".format(letter)] = str(phase - 1)
            self.params["o_CLKO{}".format(n_to_l[n])] = clk

            # In theory this really shouldn't be necessary, in practice
            # the tooling seems to have suspicous clock latency values
            # on generated clocks that are causing timing problems and Lattice
            # hasn't responded to my support requests on the matter.
            if self.platform and self.create_output_port_clocks:
                self.platform.add_platform_command("create_clock -period {} -name {} [get_pins {}.PLL_inst/CLKO{}]".format(str(1/f*1e9), self.name + "_" + n_to_l[n],self.name, n_to_l[n]))

        if self.platform and self.create_output_port_clocks:
            i = 0
        self.specials += Instance("PLL", name = self.name, **self.params)

    # The gist of calculating the analog parameters is to run through all the
    # permutations of the parameters and find the optimum set of values based
    # on the transfer function of the PLL loop filter. There are constraints on
    # on a few specific parameters, the open loop transfer function, and the closed loop
    # transfer function. An optimal solution is chosen based on the bandwidth
    # of the response relative to the input reference frequency of the PLL.

    # Later revs of the Lattice calculator BW_FACTOR is set to 10, may need to change it
    def calc_optimal_params(self, fref, fbkdiv, M = 1, BW_FACTOR = 5):
        print("Calculating Analog Paramters for a reference freqeuncy of " + str(fref*1e-6) +
              " Mhz, feedback div " + str(fbkdiv) + ", and input div " + str(M) + "."
        )

        best_params = None
        best_3db = 0

        for params in self.transfer_func_coefficients:
            closed_loop_peak = self.closed_loop_peak(fbkdiv, params)
            if (closed_loop_peak["peak"] < 0.8 or
               closed_loop_peak["peak"] > 1.35):
                continue

            open_loop_crossing = self.open_loop_crossing(fbkdiv, params)
            if open_loop_crossing["phase"] <= 45:
                continue

            closed_loop_3db = self.closed_loop_3db(fbkdiv, params)
            bw_factor = fref*1e6 / M / closed_loop_3db["f"]
            if bw_factor < BW_FACTOR:
                continue

            if best_3db < closed_loop_3db["f"]:
                best_3db = closed_loop_3db["f"]
                best_params = params

        print("Done calculating analog parameters:")
        HDL_params = self.numerical_params_to_HDL_params(best_params)
        pprint.pprint(HDL_params)

        return HDL_params


    def numerical_params_to_HDL_params(self, params):
        IPP_SEL_LUT = {1: 1, 2: 3, 3: 7, 4: 15}
        ret = {
            "CRIPPLE": str(int(params.CRIPPLE / 1e-12)) + "P",
            "CSET": str(int((params.CSET / 4e-12)*4)) + "P",
            "V2I_PP_RES": "{0:g}".format(params.V2I_PP_RES/1e3).replace(".","P") + "K",
            "IPP_CTRL": "0b{0:04b}".format(int(params.IPP_CTRL / 1e-6 + 3)),
            "IPI_CMP": "0b{0:04b}".format(int(params.IPI_CMP / .5e-6)),
            "BW_CTL_BIAS": "0b{0:04b}".format(params.BW_CTL_BIAS),
            "IPP_SEL": "0b{0:04b}".format(IPP_SEL_LUT[params.IPP_SEL]),
        }

        return ret

    def calc_valid_io_i2(self):
        # Valid permutations of IPP_CTRL, BW_CTL_BIAS, IPP_SEL, and IPI_CMP paramters are constrained
        # by the following equation so we can narrow the problem space by calculating the
        # them early in the process.
        # ip = 5.0/3 * ipp_ctrl*bw_ctl_bias*ipp_sel
        # ip/ipi_cmp == 50 +- 1e-4

        self.valid_io_i2_permutations = []

        # List out the valid values of each parameter
        IPP_CTRL_VALUES = range(1,4+1)
        IPP_CTRL_UNITS = 1e-6
        IPP_CTRL_VALUES = [element * IPP_CTRL_UNITS for element in IPP_CTRL_VALUES]
        BW_CTL_BIAS_VALUES = range(1,15+1)
        IPP_SEL_VALUES = range(1,4+1)
        IPI_CMP_VALUES = range(1,15+1)
        IPI_CMP_UNITS = 0.5e-6
        IPI_CMP_VALUES = [element * IPI_CMP_UNITS for element in IPI_CMP_VALUES]

        for IPP_CTRL in IPP_CTRL_VALUES:
            for BW_CTL_BIAS in BW_CTL_BIAS_VALUES:
                for IPP_SEL in IPP_SEL_VALUES:
                    for IPI_CMP in IPI_CMP_VALUES:
                        is_valid_io_i2 = self.is_valid_io_i2(IPP_CTRL, BW_CTL_BIAS, IPP_SEL, IPI_CMP)
                        if is_valid_io_i2 and self.is_unique_io(is_valid_io_i2['io']):
                            self.valid_io_i2_permutations.append( io_i2(
                                is_valid_io_i2['io'], is_valid_io_i2['i2'],
                                IPP_CTRL, BW_CTL_BIAS, IPP_SEL
                            ) )

    def is_unique_io(self, io):
        return not any(x.io == io for x in self.valid_io_i2_permutations)

    def is_valid_io_i2(self, IPP_CTRL, BW_CTL_BIAS, IPP_SEL, IPI_CMP):
        tolerance = 1e-4
        ip = 5.0/3.0 * IPP_CTRL * BW_CTL_BIAS * IPP_SEL
        i2 = IPI_CMP
        if abs(ip/i2-50) < tolerance:
            return {'io':ip,'i2':i2}
        else:
            return False

    def calc_tf_coefficients(self):
        # Take the permutations of the various analog parameters
        # then precalculate the coefficients of the transfer function.
        # During the final calculations sub in the feedback divisor
        # to get the final transfer functions.

        #       (ABF+EC)s^2 + (A(F(G+1)+B) + ED)s + A(G+1)          C1s^s + C2s + C3
        # tf = -------------------------------------------- =  --------------------------
        #               ns^2(CFs^2 + (DF+C)s + D)                ns^2(C4s^2 + C5s + C6)

        # A = i2*g3*ki
        # B = r1*c3
        # C = B*c2
        # D = c2+c3
        # E = io*ki*k1
        # F = r*cs
        # G = k3
        # n = total divisor of the feedback signal (output + N)

        # Constants
        c3 = 20e-12
        g3 = 0.2952e-3
        k1 = 6
        k3 = 100
        ki = 508e9
        r1 = 9.8e6
        B = r1*c3

        # PLL Parameters
        CSET_VALUES = range(2,17+1)
        CSET_UNITS = 4e-12
        CSET_VALUES = [element * CSET_UNITS for element in CSET_VALUES]
        CRIPPLE_VALUES = [1, 3, 5, 7, 9, 11, 13, 15]
        CRIPPLE_UNITS = 1e-12
        CRIPPLE_VALUES = [element * CRIPPLE_UNITS for element in CRIPPLE_VALUES]
        V2I_PP_RES_VALUES = [9000, 9300, 9700, 10000, 10300, 10700, 11000, 11300]

        self.transfer_func_coefficients = []

        # Run through all the permutations and cache it all
        for io_i2 in self.valid_io_i2_permutations:
            for CSET in CSET_VALUES:
                for CRIPPLE in CRIPPLE_VALUES:
                    for V2I_PP_RES in V2I_PP_RES_VALUES:
                        A = io_i2.i2*g3*ki
                        B = r1*c3
                        C = B*CSET
                        D = CSET+c3
                        E = io_i2.io*ki*k1
                        F = V2I_PP_RES*CRIPPLE
                        G = k3

                        self.transfer_func_coefficients.append( nx_pll_param_permutation(
                            A*B*F+E*C, # C1
                            A*(F*(G+1)+B)+E*D, # C2
                            A*(G+1), # C3
                            C*F, # C4
                            D*F+C, # C5
                            D, # C6
                            io_i2.IPP_CTRL, io_i2.BW_CTL_BIAS, io_i2.IPP_SEL,
                            CSET, CRIPPLE, V2I_PP_RES, io_i2.i2
                        ))

    def calc_tf(self, n, s, params):
        return ( (params.C1 * s ** 2 + params.C2 * s + params.C3) /
                ( n * s ** 2 * (params.C4 * s ** 2 + params.C5 * s + params.C6) ) )

    def closed_loop_peak(self, fbkdiv, params):
        f = 1e6
        step = 1.1
        step_divs = 0

        peak_value = -99
        peak_f = 0

        last_value = -99

        while f < 1e9:
            s = 1j * 2 * pi * f
            tf_value = self.calc_tf(fbkdiv, s, params)
            this_result = 20*log10(abs(tf_value/(1+tf_value)))
            if this_result > peak_value:
                peak_value = this_result
                peak_f = f

            if this_result < last_value and step_divs < 5:
                f = f/(step**2)
                step = (step - 1) * .5 + 1
                step_divs = step_divs + 1
            elif this_result < last_value and step_divs == 5:
                break
            else:
                last_value = this_result
                f = f * step

        return {"peak":peak_value, "peak_freq":peak_f}

    def closed_loop_3db(self, fbkdiv, params):
        f = 1e6
        step = 1.1
        step_divs = 0

        last_f = 1

        while f < 1e9:
            s = 1j * 2 * pi * f
            tf_value = self.calc_tf(fbkdiv, s, params)
            this_result = 20*log10(abs(tf_value/(1+tf_value)))

            if (this_result+3) < 0 and step_divs < 5:
                f = last_f
                step = (step - 1) * .5 + 1
                step_divs = step_divs + 1
            elif (this_result+3) < 0 and step_divs == 5:
                break
            else:
                last_f = f
                f = f * step

        return {"f":last_f}

    def open_loop_crossing(self, fbkdiv, params):
        f = 1e6
        step = 1.1
        step_divs = 0

        last_f = 1
        last_tf = 0

        while f < 1e9:
            s = 1j * 2 * pi * f
            tf_value = self.calc_tf(fbkdiv, s, params)
            this_result = 20*log10(abs(tf_value))

            if this_result < 0 and step_divs < 5:
                f = last_f
                step = (step - 1) * .5 + 1
                step_divs = step_divs + 1
            elif this_result < 0 and step_divs == 5:
                break
            else:
                last_f = f
                last_tf = tf_value
                f = f * step

        return {"f":last_f, "phase":phase(-last_tf)*180/pi}
