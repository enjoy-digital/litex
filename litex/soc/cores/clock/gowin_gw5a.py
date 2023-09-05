#
# This file is part of LiteX.
#
# Copyright (c) 2023 Icenowy Zheng <icenowy@aosc.io>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

from litex.soc.cores.clock.common import *

# GoWin / GW5APLL ----------------------------------------------------------------------------------

class GW5APLL(LiteXModule):
    nclkouts_max = 7

    def __init__(self, devicename, device, vco_margin=0):
        self.logger = logging.getLogger("GW5APLL")
        self.logger.info("Creating GW5APLL.".format())
        self.device     = device
        self.devicename = devicename
        self.vco_margin = vco_margin
        self.reset      = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}
        self.vco_freq_range = self.get_vco_freq_range(device)
        self.pfd_freq_range = self.get_pfd_freq_range(device)

    @staticmethod
    def get_vco_freq_range(device):
        vco_freq_range = None
        if device.startswith('GW5A-'):
            vco_freq_range = (800e6, 1600e6) # As restricted by Gowin toolchain 1.9.9b3
        elif device.startswith('GW5A-') or device.startswith('GW5AT-') or device.startswith('GW5AST-'):
            vco_freq_range = (800e6, 2000e6) # datasheet values
        if vco_freq_range is None:
            raise ValueError(f"Unsupported device {device}.")
        return vco_freq_range

    @staticmethod
    def get_pfd_freq_range(device):
        pfd_freq_range = None
        if device.startswith('GW5A-'):
            pfd_freq_range = (19e6, 400e6) # As restricted by Gowin toolchain 1.9.9b3
        elif device.startswith('GW5AT-') or device.startswith('GW5AST-'):
            pfd_freq_range = (10e6, 400e6) # datasheet values
        if pfd_freq_range is None:
            raise ValueError(f"Unsupported device {device}.")
        return pfd_freq_range

    def register_clkin(self, clkin, freq):
        self.clkin = Signal()
        if isinstance(clkin, (Signal, ClockSignal)):
            self.comb += self.clkin.eq(clkin)
        else:
            raise ValueError
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, margin=1e-2, with_reset=True):
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, phase, margin)
        if with_reset:
            self.specials += AsyncResetSynchronizer(cd, ~self.locked)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        configs = [] # corresponding VCO/FBDIV/IDIV/ODIV params + diff

        for idiv in range(1, 64):
            pfd_freq = self.clkin_freq/idiv
            pfd_freq_min, pfd_freq_max = self.pfd_freq_range
            if (pfd_freq < pfd_freq_min) or (pfd_freq > pfd_freq_max):
                continue
            for fdiv in range(1, 64):
                for mdiv in range(2,128):
                    vco_freq = self.clkin_freq/idiv*fdiv*mdiv
                    (vco_freq_min, vco_freq_max) = self.vco_freq_range
                    if (vco_freq >= vco_freq_min*(1 + self.vco_margin) and
                        vco_freq <= vco_freq_max*(1 - self.vco_margin)):
                            okay = True
                            config = {}
                            for n, (clk, f, p, m) in self.clkouts.items():
                                odiv = round(vco_freq/f)
                                out_freq = vco_freq/odiv
                                diff = abs(out_freq - f) / f
                                pe = round(p * odiv / 360)
                                if abs((360.0 * pe / odiv) - p) / 360 > m:
                                    okay = False
                                if diff > m:
                                    okay = False
                                else:
                                    config["odiv%d" % n] = odiv
                                    config["diff%d" % n] = diff
                                    config["pe%d" % n] = int(p * odiv / 360)
                                    config["pe%d_fine" % n] = round(p * odiv * 8 / 360) % 8
                            if okay:
                                config["idiv"] = idiv
                                config["vco"] = vco_freq
                                config["fdiv"] = fdiv
                                config["mdiv"] = mdiv
                                configs += [config]

        if len(configs) == 0:
            raise ValueError("No PLL config found")

        best_config = None
        best_diff_sum = 0
        for i in range(0,len(configs)):
            curr_diff_sum = 0
            for n, clkout in self.clkouts.items():
                curr_diff_sum += configs[i]["diff%d" % n]

            if i == 0 or curr_diff_sum < best_diff_sum:
                best_diff_sum = curr_diff_sum
                best_config = configs[i]

        return best_config

    def do_finalize(self):
        assert hasattr(self, "clkin")
        assert len(self.clkouts) > 0 and len(self.clkouts) <= self.nclkouts_max
        config = self.compute_config()
        # Based on UG306-1.0 Note.
        self.params.update(
            # Parameters.
            p_FCLKIN           = str(self.clkin_freq/1e6), # Clk Input frequency (MHz).
            p_IDIV_SEL         = config["idiv"],           # Static IDIV value (1-64).
            p_FBDIV_SEL        = config["fdiv"],           # Static FBDIV value (1-64).
            p_ODIV0_SEL        = 8,                        # Static ODIV value (1-128).
            p_ODIV0_FRAC_SEL   = 0,                        # Static ODIV0 fractional value (0-7)/8
            p_ODIV1_SEL        = 8,                        # Static ODIV1 value
            p_ODIV2_SEL        = 8,                        # Static ODIV2 value
            p_ODIV3_SEL        = 8,                        # Static ODIV3 value
            p_ODIV4_SEL        = 8,                        # Static ODIV4 value
            p_ODIV5_SEL        = 8,                        # Static ODIV5 value
            p_ODIV6_SEL        = 8,                        # Static ODIV6 value
            p_MDIV_SEL         = config["mdiv"],           # Static MDIV value (2-128).
            p_MDIV_FRAC_SEL    = 0,                        # Static MDIV fractional value (0-7)/8
            p_CLKOUT0_EN       = "FALSE",                  # Disable CLKOUT0.
            p_CLKOUT1_EN       = "FALSE",                  # Disable CLKOUT1.
            p_CLKOUT2_EN       = "FALSE",                  # Disable CLKOUT2.
            p_CLKOUT3_EN       = "FALSE",                  # Disable CLKOUT3.
            p_CLKOUT4_EN       = "FALSE",                  # Disable CLKOUT4.
            p_CLKOUT5_EN       = "FALSE",                  # Disable CLKOUT5.
            p_CLKOUT6_EN       = "FALSE",                  # Disable CLKOUT6.
            p_CLKOUT0_DT_DIR   = 1,                        # Static CLKOUT0 duty control direction (0-down, 1-up)
            p_CLKOUT1_DT_DIR   = 1,                        # Static CLKOUT1 duty control direction (0-down, 1-up)
            p_CLKOUT2_DT_DIR   = 1,                        # Static CLKOUT2 duty control direction (0-down, 1-up)
            p_CLKOUT3_DT_DIR   = 1,                        # Static CLKOUT3 duty control direction (0-down, 1-up)
            p_CLKOUT0_DT_STEP  = 0,                        # Static CLKOUT0 duty control step (0,1,2,4)*50ps
            p_CLKOUT1_DT_STEP  = 0,                        # Static CLKOUT1 duty control step (0,1,2,4)*50ps
            p_CLKOUT2_DT_STEP  = 0,                        # Static CLKOUT2 duty control step (0,1,2,4)*50ps
            p_CLKOUT3_DT_STEP  = 0,                        # Static CLKOUT3 duty control step (0,1,2,4)*50ps
            p_CLK0_IN_SEL      = 0,                        # Select ODIV0 source (0-VCO, 1-CLKIN)
            p_CLK0_OUT_SEL     = 0,                        # Select CLKOUT0 source (0-ODIV0, 1-CLKIN)
            p_CLK1_IN_SEL      = 0,                        # Select ODIV1 source (0-VCO, 1-CLKIN)
            p_CLK1_OUT_SEL     = 0,                        # Select CLKOUT1 source (0-ODIV1, 1-CLKIN)
            p_CLK2_IN_SEL      = 0,                        # Select ODIV2 source (0-VCO, 1-CLKIN)
            p_CLK2_OUT_SEL     = 0,                        # Select CLKOUT2 source (0-ODIV2, 1-CLKIN)
            p_CLK3_IN_SEL      = 0,                        # Select ODIV3 source (0-VCO, 1-CLKIN)
            p_CLK3_OUT_SEL     = 0,                        # Select CLKOUT3 source (0-ODIV3, 1-CLKIN)
            p_CLK4_IN_SEL      = 0,                        # Select ODIV4 source (0-VCO, 1-CLKIN)
            p_CLK4_OUT_SEL     = 0,                        # Select CLKOUT4 source (0-ODIV4, 1-CLKIN)
            p_CLK5_IN_SEL      = 0,                        # Select ODIV5 source (0-VCO, 1-CLKIN)
            p_CLK5_OUT_SEL     = 0,                        # Select CLKOUT5 source (0-ODIV5, 1-CLKIN)
            p_CLKFB_SEL        = "INTERNAL",               # Clk Feedback type (INTERNAL, EXTERNAL).
            p_DYN_DPA_EN       = "FALSE",                  # Disable dynamic phase shift.
            p_CLKOUT0_PE_COARSE= 0,                        # Static CLKOUT0 phase shift coarse config
            p_CLKOUT0_PE_FINE  = 0,                        # Static CLKOUT0 phase shift fine config
            p_CLKOUT1_PE_COARSE= 0,                        # Static CLKOUT1 phase shift coarse config
            p_CLKOUT1_PE_FINE  = 0,                        # Static CLKOUT1 phase shift fine config
            p_CLKOUT2_PE_COARSE= 0,                        # Static CLKOUT2 phase shift coarse config
            p_CLKOUT2_PE_FINE  = 0,                        # Static CLKOUT2 phase shift fine config
            p_CLKOUT3_PE_COARSE= 0,                        # Static CLKOUT3 phase shift coarse config
            p_CLKOUT3_PE_FINE  = 0,                        # Static CLKOUT3 phase shift fine config
            p_CLKOUT4_PE_COARSE= 0,                        # Static CLKOUT4 phase shift coarse config
            p_CLKOUT4_PE_FINE  = 0,                        # Static CLKOUT4 phase shift fine config
            p_CLKOUT5_PE_COARSE= 0,                        # Static CLKOUT5 phase shift coarse config
            p_CLKOUT5_PE_FINE  = 0,                        # Static CLKOUT5 phase shift fine config
            p_CLKOUT6_PE_COARSE= 0,                        # Static CLKOUT6 phase shift coarse config
            p_CLKOUT6_PE_FINE  = 0,                        # Static CLKOUT6 phase shift fine config
            p_DYN_PE0_SEL      = "FALSE",                  # Static CLKOUT0 phase shift.
            p_DYN_PE1_SEL      = "FALSE",                  # Static CLKOUT1 phase shift.
            p_DYN_PE2_SEL      = "FALSE",                  # Static CLKOUT2 phase shift.
            p_DYN_PE3_SEL      = "FALSE",                  # Static CLKOUT3 phase shift.
            p_DYN_PE4_SEL      = "FALSE",                  # Static CLKOUT4 phase shift.
            p_DYN_PE5_SEL      = "FALSE",                  # Static CLKOUT5 phase shift.
            p_DYN_PE6_SEL      = "FALSE",                  # Static CLKOUT6 phase shift.
            p_DE0_EN           = "FALSE",                  # Disable CLKOUT0 duty cycle adjust
            p_DE1_EN           = "FALSE",                  # Disable CLKOUT0 duty cycle adjust
            p_DE2_EN           = "FALSE",                  # Disable CLKOUT0 duty cycle adjust
            p_DE3_EN           = "FALSE",                  # Disable CLKOUT0 duty cycle adjust
            p_DE4_EN           = "FALSE",                  # Disable CLKOUT0 duty cycle adjust
            p_DE5_EN           = "FALSE",                  # Disable CLKOUT0 duty cycle adjust
            p_DE6_EN           = "FALSE",                  # Disable CLKOUT0 duty cycle adjust
            p_RESET_I_EN       = "FALSE",                  # -
            p_RESET_O_EN       = "FALSE",                  # -
            p_SSC_EN           = "FALSE",                  # Disable spread spectrun control.

            # Inputs.
            i_CLKIN         = self.clkin,     # Clk Input.
            i_CLKFB         = 0,              # Clk Feedback.
            i_RESET         = self.reset,     # PLL Reset.
            i_PLLPWD        = 0,              # PLL Power Down.
            i_RESET_I       = 0,              # PLL Partial Reset (for testing)
            i_RESET_O       = 0,              # PLL Partial Reset (for testing)
            i_PSDIR         = 0,              # Dynamic Phase Select direction.
            i_PSSEL         = Constant(0, 3), # Dynamic Phase Select channel control.
            i_PSPULSE       = 0,              # Dynamic Phase Select pulse.
            i_SSCPOL        = 0,              # Spread Spectrum polarity.
            i_SSCON         = 0,              # Spread Spectrum enable.
            i_SSCMDSEL      = Constant(0, 7), # Dynamic SSC MDIV integer control.
            i_SSCMDSEL_FRAC = Constant(0, 3), # Dynamic SSC MDIV fractional control.

            o_LOCK     = self.locked,
            o_CLKOUT0  = Open(),
            o_CLKOUT1  = Open(),
            o_CLKOUT2  = Open(),
            o_CLKOUT3  = Open(),
            o_CLKOUT4  = Open(),
            o_CLKOUT5  = Open(),
            o_CLKOUT6  = Open(),
            o_CLKFBOUT = Open()
        )

        if self.device.startswith('GW5A-'): # GW5A-25, uses PLLA
            instance_name = 'PLLA'
            self.params.update(
                i_MDCLK  = 0,
                i_MDOPC  = Constant(0, 2),
                i_MDAINC = 0,
                i_MDWDI  = Constant(0, 8),
            )
        else: # GW5A{,S}T, uses PLL
            instance_name = 'PLL'
            self.params.update(
                p_DYN_IDIV_SEL     = "FALSE", # Disable dynamic IDIV.
                p_DYN_FBDIV_SEL    = "FALSE", # Disable dynamic FBDIV.
                p_DYN_ODIV0_SEL    = "FALSE", # Disable dynamic ODIV0.
                p_DYN_ODIV1_SEL    = "FALSE", # Disable dynamic ODIV1.
                p_DYN_ODIV2_SEL    = "FALSE", # Disable dynamic ODIV2.
                p_DYN_ODIV3_SEL    = "FALSE", # Disable dynamic ODIV3.
                p_DYN_ODIV4_SEL    = "FALSE", # Disable dynamic ODIV4.
                p_DYN_ODIV5_SEL    = "FALSE", # Disable dynamic ODIV5.
                p_DYN_ODIV6_SEL    = "FALSE", # Disable dynamic ODIV6.
                p_DYN_DT0_SEL      = "FALSE", # Static CLKOUT0 duty control.
                p_DYN_DT1_SEL      = "FALSE", # Static CLKOUT1 duty control.
                p_DYN_DT2_SEL      = "FALSE", # Static CLKOUT2 duty control.
                p_DYN_DT3_SEL      = "FALSE", # Static CLKOUT3 duty control.
                p_DYN_ICP_SEL      = "FALSE", # Static ICP_SEL.
                # ICP_SEL determined by the toolchain
                p_DYN_LPF_SEL      = "FALSE", # Static LPF_RES/LPF_CAP;
                # LPF_RES/LPF_CAP determined by the toolchain

                i_FBDSEL      = Constant(0, 6), # Dynamic FBDIV control.
                i_IDSEL       = Constant(0, 6), # Dynamic IDIV control.
                i_MDSEL       = Constant(0, 7), # Dynamic MDIV integer control.
                i_MDSEL_FRAC  = Constant(0, 3), # Dynamic MDIV fractional control.
                i_ODSEL0      = Constant(0, 7), # Dynamic ODIV0 integer control.
                i_ODSEL0_FRAC = Constant(0, 3), # Dynamic ODIV0 fractional control.
                i_ODSEL1      = Constant(0, 7), # Dynamic ODIV1 control.
                i_ODSEL2      = Constant(0, 7), # Dynamic ODIV2 control.
                i_ODSEL3      = Constant(0, 7), # Dynamic ODIV3 control.
                i_ODSEL4      = Constant(0, 7), # Dynamic ODIV4 control.
                i_ODSEL5      = Constant(0, 7), # Dynamic ODIV5 control.
                i_ODSEL6      = Constant(0, 7), # Dynamic ODIV6 control.
                i_DT0         = Constant(0, 4), # Dynamic duty cycle control for CLKOUT0.
                i_DT1         = Constant(0, 4), # Dynamic duty cycle control for CLKOUT1.
                i_DT2         = Constant(0, 4), # Dynamic duty cycle control for CLKOUT2.
                i_DT3         = Constant(0, 4), # Dynamic duty cycle control for CLKOUT3.
                i_ENCLK0      = 1,              # Dynamic CLKOUT0 enable.
                i_ENCLK1      = 1,              # Dynamic CLKOUT1 enable.
                i_ENCLK2      = 1,              # Dynamic CLKOUT2 enable.
                i_ENCLK3      = 1,              # Dynamic CLKOUT3 enable.
                i_ENCLK4      = 1,              # Dynamic CLKOUT4 enable.
                i_ENCLK5      = 1,              # Dynamic CLKOUT5 enable.
                i_ENCLK6      = 1,              # Dynamic CLKOUT6 enable.
                i_ICPSEL      = Constant(0, 6), # Dynamic ICP current control.
                i_LPFRES      = Constant(0, 3), # Dynamic LPFRES control.
                i_LPFCAP      = Constant(0, 2), # Dynamic LPFCAP control.
            )

        for i in range(0, len(self.clkouts)):
            clk, f, p, m = self.clkouts[i]
            self.params["o_CLKOUT%d" % i] = clk
            self.params["p_CLKOUT%d_EN" % i] = "TRUE"
            self.params["p_ODIV%d_SEL" % i] = config["odiv%d" % i]
            self.params["p_CLKOUT%d_PE_COARSE" % i] = config["pe%d" % i]
            self.params["p_CLKOUT%d_PE_FINE" % i] = config["pe%d_fine" % i]

        self.specials += Instance(instance_name, **self.params)
