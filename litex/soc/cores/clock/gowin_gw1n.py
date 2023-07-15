#
# This file is part of LiteX.
#
# Copyright (c) 2021-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

from litex.soc.cores.clock.common import *

# GoWin / GW1NOSC ----------------------------------------------------------------------------------

class GW1NOSC(LiteXModule):
    osc_div_range = (2,  128)
    def __init__(self, device, freq, margin=1e-2):
        self.logger = logging.getLogger("GW1NOSC")
        self.logger.info("Creating GW1NOSC.".format())
        self.clk    = Signal()

        # # #

        # Oscillator frequency.
        osc_freq   = 250e6
        if device in ["GW1N-4", "GW1NR-4", "GW1N-4B", "GW1NR-4B", "GW1NRF-4B", "GW1N-4C", "GW1NR-4C"]:
            osc_freq = 210e6

        # Oscillator divider.
        osc_div = None
        osc_div_min, osc_div_max = self.osc_div_range
        for div in range(osc_div_min, osc_div_max):
            clk_freq = osc_freq/div
            if (clk_freq >= freq*(1 - margin) and clk_freq <= freq*(1 + margin)):
                osc_div = div
        if osc_div is None:
            raise ValueError("No OSC config found")
        self.logger.info(f"Configured to {(osc_freq/osc_div)/1e6:3.2f}MHz (div={osc_div}).")

        # Oscillator instance.
        self.specials += Instance("OSC",
            p_DEVICE   = device,
            p_FREQ_DIV = osc_div,
            o_OSCOUT   = self.clk
        )

# GoWin / GW1NPLL ----------------------------------------------------------------------------------

class GW1NPLL(LiteXModule):
    nclkouts_max = 4

    def __init__(self, devicename, device, vco_margin=0):
        self.logger = logging.getLogger("GW1NPLL")
        self.logger.info("Creating GW1NPLL.".format())
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
        if device.startswith('GW1NS'):
            if 'C7/I6' in device or 'C6/I5' in device:
                vco_freq_range = (600e6, 1200e6)  # datasheet says (400, 1200) but compiler enforces (600, 1200)
            elif 'C5/I4' in device:
                vco_freq_range = (320e6, 960e6)  # datasheet values, not tested
        elif device.startswith('GW1N-1S'):
            vco_freq_range = (400e6, 1200e6)
        elif device.startswith('GW1N-') or device.startswith('GW1NR-'):
            vco_freq_range = (400e6, 900e6)
        if vco_freq_range is None:
            raise ValueError(f"Unsupported device {device}.")
        return vco_freq_range

    @staticmethod
    def get_pfd_freq_range(device):
        pfd_freq_range = None
        if device.startswith('GW1NS'):
            if 'C7/I6' in device or 'C6/I5' in device:
                pfd_freq_range = (3e6, 400e6)
            elif 'C5/I4' in device:
                pfd_freq_range = (3e6, 320e6)
        elif device.startswith('GW1N-1S'):
            pfd_freq_range = (3e6, 400e6)  # not verified: not found in the datasheet
        elif device.startswith('GW1N-') or device.startswith('GW1NR-'):
            pfd_freq_range = (3e6, 400e6)  # not verified: not found in the datasheet
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
            # FIXME: Should use PLL's lock but does not seem stable.
            self.specials += AsyncResetSynchronizer(cd, self.reset)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        # extract the highest frequency and associated margin
        freq_max, m = max([(f, n) for (_, f, _, n) in self.clkouts.values()], key=lambda p: p[1])

        configs = [] # corresponding VCO/FBDIV/IDIV/ODIV params + diff

        for idiv in range(1, 64):
            pfd_freq = self.clkin_freq/idiv
            pfd_freq_min, pfd_freq_max = self.pfd_freq_range
            if (pfd_freq < pfd_freq_min) or (pfd_freq > pfd_freq_max):
                continue
            for fdiv in range(1, 64):
                out_freq = self.clkin_freq*fdiv/idiv
                for odiv in [2, 4, 8, 16, 32, 48, 64, 80, 96, 112, 128]:
                    vco_freq = out_freq*odiv
                    (vco_freq_min, vco_freq_max) = self.vco_freq_range
                    if (vco_freq >= vco_freq_min*(1 + self.vco_margin) and
                        vco_freq <= vco_freq_max*(1 - self.vco_margin)):
                            diff = abs(out_freq - freq_max)
                            if diff <= freq_max*m:
                                configs.append({
                                    "diff" : diff,
                                    "idiv" : idiv,
                                    "odiv" : odiv,
                                    "vco"  : vco_freq,
                                    "fdiv" : fdiv
                                })
        if len(configs) == 0:
            raise ValueError("No PLL config found")

        # select better combo (where diff f_real-f_req is the smallest)
        config = configs[min([(i, v["diff"]) for i, v in enumerate(configs)], key=lambda p: p[1])[0]]

        # out_freq using the selected configuration
        out_freq = self.clkin_freq*config["fdiv"] / config["idiv"]

        # Phase
        phases = list({p for (_, _, p, _) in self.clkouts.values() if p != 0})
        assert len(phases) < 2 # only zero or one phase possible
        # configure phase param
        config["PSDA_SEL"] = f"{int(phases[0] // 22.5):04b}" if len(phases) == 1 else "0000"

        # frequencies
        # CLKOUT & CLKOUTP : VCODIV / 1
        # CLKOUTD3         : VCODIV / 3
        # CLKOUTD          : VCODIV / an even value [2-128]
        # FIXME: bypass may used to directly connect output clock to the input
        freqs_div = [freq_max // f for (_, f, _, _) in self.clkouts.values() if freq_max // f != 1]

        if len(freqs_div) > 2:
            raise ValueError("Gowin PLL can't have more than two divisor")

        clkoutd_div = [d for d in freqs_div if d != 3] # extracts divisor by an even value
        if (len(freqs_div) == 2 and freqs_div.count(3) == 2) or (len(clkoutd_div) == 2) or \
                (len(clkoutd_div) == 1 and clkoutd_div[0] % 2 != 0):
            raise ValueError("Gowin PLL has two divisor: one /3 and an even divisor between 2 and 128")

        # configure sdiv for CLKOUTD (if it's required)
        config["SDIV_SEL"] = int(clkoutd_div[0]) if len(clkoutd_div) == 1 else 2

        for c, (clock, freq, phase, margin) in self.clkouts.items():
            th_div = int(freq_max // freq) # divisor to apply
            r_freq = out_freq / th_div     # real frequency
            diff_f = abs(r_freq - freq)    # diff between obtained and requested
            # check if value fit criterion
            if diff_f > r_freq*margin:
                raise ValueError(f"Can't obtain requested frequency {diff_f} > {r_freq * margin}")
            if th_div == 1: # no divisor: may be CLKOUT or CLKOUTP
                if phase == 0:
                    out = "" # CLKOUT
                else:
                    if "CLKOUTP" in config.keys():
                        raise ValueError("Only one clock with freq == freq max and a phase != 0")
                    out = "P"
            elif th_div == 3:
                out = "D3"
            else:
                out = "D"

            config.update({
                f"CLKOUT{out}"     : clock,
                f"CLKOUT{out}_SRC" : "CLKOUT" if phase == 0 else "CLKOUTP",
            })

        return config

    def do_finalize(self):
        assert hasattr(self, "clkin")
        assert len(self.clkouts) > 0 and len(self.clkouts) <= 4
        config = self.compute_config()
        # Based on UG286-1.3E Note.
        self.params.update(
            # Parameters.
            p_DEVICE           = self.devicename,          # FPGA Device.
            p_FCLKIN           = str(self.clkin_freq/1e6), # Clk Input frequency (MHz).
            p_DYN_IDIV_SEL     = "false",                  # Disable dynamic IDIV.
            p_IDIV_SEL         = config["idiv"]-1,         # Static IDIV value (1-64).
            p_DYN_FBDIV_SEL    = "false",                  # Disable dynamic FBDIV.
            p_FBDIV_SEL        = config["fdiv"]-1,         # Static FBDIV value (1-64).
            p_DYN_ODIV_SEL     = "false",                  # Disable dynamic ODIV.
            p_ODIV_SEL         = config["odiv"],           # Static ODIV value.
            p_PSDA_SEL         = config["PSDA_SEL"],       # -
            p_DYN_DA_EN        = "false",                  # -
            p_DUTYDA_SEL       = "1000",                   # -
            p_CLKOUT_FT_DIR    = 1,                        # -
            p_CLKOUTP_FT_DIR   = 1,                        # -
            p_CLKOUT_DLY_STEP  = 0,                        # -
            p_CLKOUTP_DLY_STEP = 0,                        # -
            p_CLKFB_SEL        = "internal",               # Clk Feedback type (internal, external).
            p_CLKOUT_BYPASS    = "false",                  # Clk Input to CLKOUT bypass.
            p_CLKOUTP_BYPASS   = "false",                  # Clk Input to CLKOUTP bypass.
            p_CLKOUTD_BYPASS   = "false",                  # Clk Input to CLKOUTD bypass.
            p_DYN_SDIV_SEL     = config["SDIV_SEL"],       # Disable dynamic SDIV.

            # Inputs.
            i_CLKIN   = self.clkin,     # Clk Input.
            i_CLKFB   = 0,              # Clk Feedback.
            i_RESET   = self.reset,     # PLL Reset.
            i_RESET_P = 0,              # PLL Power Down.
            i_ODSEL   = Constant(0, 6), # Dynamic ODIV control.
            i_FBDSEL  = Constant(0, 6), # Dynamic IDIV control.
            i_IDSEL   = Constant(0, 6), # Dynamic FDIV control.
            i_PSDA    = Constant(0, 4), # Dynamic phase control.
            i_DUTYDA  = Constant(0, 4), # Dynamic duty cycle control.
        )

        # Dynamic CLKOUTP delay control. UG286 table 5-9
        if self.device.startswith("GW1N-1"):
            self.params.update(i_FDLY=Constant(0, 4))
        else:
            self.params.update(i_FDLY=Constant(0xf, 4))

        if self.device.startswith('GW1NS'):
            instance_name = 'PLLVR'
            self.params.update(i_VREN=1)
        else:
            instance_name = 'PLL'
            self.params.update(
                i_RESET_I = 0,          # IDIV reset.
                i_RESET_S = 0,          # SDIV and DIV3 reset.
            )
        for clk_name in ["CLKOUT", "CLKOUTP", "CLKOUTD", "CLKOUTD3"]:
            self.params[f"o_{clk_name}"] = config.get(clk_name, Open()) # Clock output.
            if clk_name in ["CLKOUTD", "CLKOUTD3"]: # Recopy CLKOUTx to CLKOUTDx
                self.params[f"p_{clk_name}_SRC"] = config.get(f"{clk_name}_SRC", "CLKOUT")

        self.params.update(o_LOCK=self.locked) # PLL lock status.
        self.specials += Instance(instance_name, **self.params)
