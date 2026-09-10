#
# This file is part of LiteX.
#
# Copyright (c) 2021-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import re

from migen import *

from litex.gen import *

from litex.soc.cores.clock.common import *

# GoWin / GW1NOSC ----------------------------------------------------------------------------------

class GW1NOSC(LiteXModule):
    osc_div_range = (2,  128)
    def __init__(self, device, freq, margin=1e-2):
        check_freq_positive(freq, "Oscillator frequency")
        check_margin(margin)
        self.logger = logging.getLogger("GW1NOSC")
        self.logger.info("Creating GW1NOSC.".format())
        self.clk    = Signal()

        # # #

        # Oscillator frequency.
        osc_freq   = 250e6
        if device in ["GW1N-4", "GW1NR-4", "GW1N-4B", "GW1NR-4B", "GW1NRF-4B", "GW1N-4C", "GW1NR-4C"]:
            osc_freq = 210e6

        # Oscillator divider.
        best_config = None
        osc_div_min, osc_div_max = self.osc_div_range
        for div in range(osc_div_min, osc_div_max):
            clk_freq = osc_freq/div
            error    = clkout_freq_error(clk_freq, freq)
            if error <= margin and (best_config is None or error < best_config["error"]):
                best_config = {"error": error, "freq": clk_freq, "div": div}
        if best_config is None:
            raise ValueError("No OSC config found")
        osc_div = best_config["div"]
        self.config = best_config
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

    def __init__(self, devicename, device, vco_margin=0, name=None):
        check_margin(vco_margin, "VCO margin")
        self.logger = logging.getLogger("GW1NPLL")
        self.logger.info("Creating GW1NPLL.".format())
        self.device     = device
        self.devicename = devicename
        self.name       = name
        self.vco_margin = vco_margin
        self.reset      = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}
        self.primitive      = self.get_primitive(devicename)
        self.vco_freq_range = self.get_vco_freq_range(device, devicename)
        self.pfd_freq_range = self.get_pfd_freq_range(device, devicename)

    @staticmethod
    def get_device_model(devicename):
        # A/B/C/D are die revisions; retain functional suffixes such as 1S and 1P5.
        return re.sub(r"[ABCD]$", "", devicename)

    @staticmethod
    def get_speed_grade(device):
        match = re.search(r"C([0-9]+)(?:/I([0-9]+))?$|I([0-9]+)$", device)
        if match is None:
            return None
        if match.group(1) is not None:
            grade = int(match.group(1))
            if match.group(2) is not None and int(match.group(2)) != grade - 1:
                raise ValueError(f"Unsupported speed grade in {device}.")
            return grade
        return int(match.group(3)) + 1

    @classmethod
    def get_primitive(cls, devicename):
        # Gowin UG286, Tables 5-1 and 5-10; rPLL/PLLVR IP device lists.
        model = cls.get_device_model(devicename)
        if model in ("GW1NS-4", "GW1NSR-4", "GW1NSER-4"):
            return "PLLVR"
        if model in (
            "GW1N-1", "GW1N-1S", "GW1N-4", "GW1N-9",
            "GW1NR-1", "GW1NR-4", "GW1NR-9", "GW1NRF-4",
            "GW1NS-2", "GW1NSR-2", "GW1NSE-2", "GW1NZ-1",
            "GW1A-1", "GW1AN-1",
        ):
            return "rPLL"
        raise ValueError(f"Unsupported rPLL/PLLVR device {devicename}.")

    @classmethod
    def get_freq_ranges(cls, device, devicename=None):
        if devicename is None:
            # Retain support for frequency queries using a full part number.
            match = re.match(r"(GW1[A-Z]*)-(?:LV|UV|EV|ZV)?([0-9]+(?:P5|S)?)", device)
            if match is None:
                raise ValueError(f"Unsupported device {device}.")
            devicename = "-".join(match.groups())
        model = cls.get_device_model(devicename)
        primitive = cls.get_primitive(devicename)
        grade = cls.get_speed_grade(device)

        # Values are (VCO minimum, VCO maximum, PFD maximum), in MHz.
        # DS100, DS117, DS821, DS861, DS871, DS881, DS891, DS1501 and DS186.
        if model in ("GW1N-1", "GW1NR-1"):
            ranges = {5: (320, 720, 320), 6: (400, 900, 400), 7: (400, 900, 400)}
        elif model == "GW1N-4":
            ranges = {5: (320, 800, 320), 6: (400, 1000, 400), 7: (400, 1000, 400)}
        elif model == "GW1NR-4":
            ranges = {6: (400, 1000, 400), 7: (400, 1000, 400)}
        elif model == "GW1NRF-4":
            ranges = {5: (320, 800, 320), 6: (400, 1000, 400)}
        elif model in ("GW1N-9", "GW1NR-9"):
            ranges = {6: (400, 1200, 400), 7: (400, 1200, 400)}
        elif model in ("GW1A-1", "GW1AN-1"):
            ranges = {6: (400, 900, 400)}
        elif model == "GW1N-1S":
            # Legacy GW1N-1S limits from DS100-2.9.4.
            ranges = {5: (320, 960, 320), 6: (400, 1200, 400), 7: (400, 1200, 400)}
        elif model == "GW1NZ-1":
            # DS841: the low-voltage ZV parts have different PLL limits.
            if "-ZV" in device:
                ranges = {3: (100, 200, 100), 4: (150, 300, 150), 5: (200, 400, 200)}
            elif "-LV" in device:
                ranges = {5: (320, 640, 320), 6: (400, 800, 400)}
            else:
                raise ValueError(f"GW1NZ PLL limits require an LV or ZV part number: {device}.")
        else:
            ranges = {5: (320, 960, 320), 6: (400, 1200, 400), 7: (400, 1200, 400)}
            if primitive == "PLLVR":
                # Keep the 600MHz lower bound enforced by the Gowin toolchain.
                ranges.update({6: (600, 1200, 400), 7: (600, 1200, 400)})

        if grade is None:
            # Without a speed grade, use the intersection of documented ranges.
            vco_min = max(r[0] for r in ranges.values())
            vco_max = min(r[1] for r in ranges.values())
            pfd_max = min(r[2] for r in ranges.values())
        elif grade in ranges:
            vco_min, vco_max, pfd_max = ranges[grade]
        else:
            raise ValueError(f"Unsupported speed grade for {devicename}: {device}.")
        return (vco_min*1e6, vco_max*1e6), (3e6, pfd_max*1e6)

    @classmethod
    def get_vco_freq_range(cls, device, devicename=None):
        return cls.get_freq_ranges(device, devicename)[0]

    @classmethod
    def get_pfd_freq_range(cls, device, devicename=None):
        return cls.get_freq_ranges(device, devicename)[1]

    def register_clkin(self, clkin, freq):
        check_freq_range(freq, self.pfd_freq_range, "Input clock frequency")
        self.clkin = connect_clkin(self, clkin)
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, margin=1e-2, with_reset=True):
        check_freq_positive(freq, "Output clock frequency")
        check_margin(margin)
        check_clkout_cd_unused(self, cd)
        check_clkout_count(self.nclkouts, self.nclkouts_max)
        clkout = Signal()
        self.clkouts[self.nclkouts] = ClkOut(clkout, freq, phase, margin)
        # FIXME: Should use PLL's lock but does not seem stable.
        connect_clkout(self, cd, clkout, reset=self.reset, with_reset=with_reset)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        check_clkin_registered(hasattr(self, "clkin"))
        check_clkouts(self.nclkouts)
        # extract the highest frequency and associated margin
        freq_max, margin = max([(clkout.freq, clkout.margin) for clkout in self.clkouts.values()], key=lambda p: p[0])

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
                            if diff <= freq_max*margin:
                                configs.append({
                                    "diff" : diff,
                                    "idiv" : idiv,
                                    "odiv" : odiv,
                                    "vco"  : vco_freq,
                                    "fdiv" : fdiv
                                })
        if len(configs) == 0:
            raise pll_config_error(self.clkin_freq, self.clkouts)

        # Phase
        phases = list({clkout.phase for clkout in self.clkouts.values() if clkout.phase != 0})
        if len(phases) >= 2:
            raise ValueError("Gowin PLL supports only one non-zero phase.")

        # frequencies
        # CLKOUT & CLKOUTP : VCODIV / 1
        # CLKOUTD3         : VCODIV / 3
        # CLKOUTD          : VCODIV / an even value [2-128]
        # FIXME: bypass may used to directly connect output clock to the input
        freqs_div = [freq_max // clkout.freq for clkout in self.clkouts.values() if freq_max // clkout.freq != 1]

        if len(freqs_div) > 2:
            raise ValueError("Gowin PLL can't have more than two divisor")

        clkoutd_div = [d for d in freqs_div if d != 3] # extracts divisor by an even value
        if (len(freqs_div) == 2 and freqs_div.count(3) == 2) or (len(clkoutd_div) == 2) or \
                (len(clkoutd_div) == 1 and clkoutd_div[0] % 2 != 0):
            raise ValueError("Gowin PLL has two divisor: one /3 and an even divisor between 2 and 128")

        # configure sdiv for CLKOUTD (if it's required)
        sdiv = int(clkoutd_div[0]) if len(clkoutd_div) == 1 else 2

        best_config = None
        best_score  = None
        for config in configs:
            config   = dict(config)
            errors   = []
            out_freq = self.clkin_freq*config["fdiv"] / config["idiv"]

            config["PSDA_SEL"] = f"{int(phases[0] // 22.5):04b}" if len(phases) == 1 else "0000"
            config["SDIV_SEL"] = sdiv

            all_valid = True
            for c, clkout in self.clkouts.items():
                th_div = int(freq_max // clkout.freq) # divisor to apply
                r_freq = out_freq / th_div     # real frequency
                error  = clkout_freq_error(r_freq, clkout.freq)
                # check if value fit criterion
                if error > clkout.margin:
                    all_valid = False
                    break
                errors.append(error)
                if th_div == 1: # no divisor: may be CLKOUT or CLKOUTP
                    if clkout.phase == 0:
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
                    f"CLKOUT{out}"     : clkout.clk,
                    f"CLKOUT{out}_SRC" : "CLKOUT" if clkout.phase == 0 else "CLKOUTP",
                })

            if all_valid:
                best_config, best_score = update_best_config(best_config, best_score, config, errors, config["vco"])

        if best_config is not None:
            return best_config
        raise pll_config_error(self.clkin_freq, self.clkouts)

    def do_finalize(self):
        check_clkin_registered(hasattr(self, "clkin"))
        check_clkouts(self.nclkouts)
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
        if self.get_device_model(self.devicename) in ("GW1N-1", "GW1N-1S"):
            self.params.update(i_FDLY=Constant(0, 4))
        else:
            self.params.update(i_FDLY=Constant(0xf, 4))

        if self.primitive == "PLLVR":
            self.params.update(i_VREN=1)
        for clk_name in ["CLKOUT", "CLKOUTP", "CLKOUTD", "CLKOUTD3"]:
            self.params[f"o_{clk_name}"] = config.get(clk_name, Open()) # Clock output.
            if clk_name in ["CLKOUTD", "CLKOUTD3"]: # Recopy CLKOUTx to CLKOUTDx
                self.params[f"p_{clk_name}_SRC"] = config.get(f"{clk_name}_SRC", "CLKOUT")

        self.params.update(o_LOCK=self.locked) # PLL lock status.
        self.specials += Instance(self.primitive, name=self.name or "", **self.params)
