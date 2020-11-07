from collections import namedtuple
import pprint
import time
import json
from math import log, log10, exp, pi
from cmath import phase

io_i2 = namedtuple('io_i2',['io', 'i2', 'IPP_CTRL', 'BW_CTL_BIAS', 'IPP_SEL'])
nexus_pll_param_permutation = namedtuple("nexus_pll_param_permutation",[
                                "C1","C2","C3","C4","C5","C6",
                                "IPP_CTRL","BW_CTL_BIAS","IPP_SEL","CSET","CRIPPLE","V2I_PP_RES","IPI_CMP"])

class NexusPLLAnalogParameters():
    # The gist of calculating the analog parameters is to run through all the
    # permutations of the parameters and find the optimum set of values based
    # on the transfer function of the PLL loop filter. There are constraints on
    # on a few specific parameters, the open loop transfer function, and the closed loop
    # transfer function. An optimal solution is chosen based on the bandwidth
    # of the response relative to the input reference frequency of the PLL.

    def __init__(self):
        self.calc_valid_io_i2()
        self.calc_tf_coefficients()

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

        print("Done calculating analog parameters.")
        print("Analog Paramters: ")
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

                        self.transfer_func_coefficients.append( nexus_pll_param_permutation(
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
