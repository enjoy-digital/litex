#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

from litex.build.generic_platform import *
from litex.soc.cores.clock.common import *

# Efinix / TRIONPLL ----------------------------------------------------------------------------------

class EFINIXPLL(LiteXModule):
    n            = 0
    nclkouts_max = 3
    def __init__(self, platform,version="V1_V2", dyn_phase_shift_pads=[]):
        self.logger = logging.getLogger("EFINIXPLL")

        if version == "V1_V2":
            self.type = "TRIONPLL"
        elif version == "V3":
            self.type = "TITANIUMPLL"
        else:
            self.logger.error("PLL version {} not supported".format(version))
            quit()

        self.logger.info("Creating {}".format(colorer(self.type, color="green")))
        self.platform   = platform
        self.nclkouts   = 0
        self.reset      = Signal()
        self.locked     = Signal()
        self.name       = f"pll{self.n}"
        EFINIXPLL.n += 1 # FIXME: Improve.

        # Create PLL block.
        block = {}
        block["type"]    = "PLL"
        block["name"]    = self.name
        block["clk_out"] = []
        block["locked"]  = self.name + "_locked"
        block["rstn"]    = self.name + "_rstn"
        block["version"] = version
        block["feedback"] = -1
        if len(dyn_phase_shift_pads) > 0:
            block["shift_ena"] = dyn_phase_shift_pads["shift_ena"]
            block["shift"]     = dyn_phase_shift_pads["shift"]
            block["shift_sel"] = dyn_phase_shift_pads["shift_sel"]
        self.platform.toolchain.ifacewriter.blocks.append(block)

        # Connect PLL's rstn/locked.
        self.comb += self.platform.add_iface_io(self.name + "_rstn").eq(~self.reset)
        self.comb += self.locked.eq(self.platform.add_iface_io(self.name + "_locked"))

    def register_clkin(self, clkin, freq, name="", refclk_name="", lvds_input=False):
        block = self.platform.toolchain.ifacewriter.get_block(self.name)

        block["input_clock_name"] = self.platform.get_pin_name(clkin)

        # If clkin has a pin number, PLL clock input is EXTERNAL
        if self.platform.get_pin_location(clkin):
            pad_name = self.platform.get_pin_location(clkin)[0]
            # PLL v1 needs pin name
            pin_name = self.platform.parser.get_pad_name_from_pin(pad_name)
            if pin_name.count("_") == 2:
                pin_name = pin_name.rsplit("_", 1)[0]
            self.platform.toolchain.excluded_ios.append(clkin)

            #tpl = "create_clock -name {clk} -period {period} [get_ports {{{clk}}}]"
            #sdc = self.platform.toolchain.additional_sdc_commands
            #sdc.append(tpl.format(clk=block["input_clock_name"], period=1/freq))

            try:
                (pll_res, clock_no) = self.platform.parser.get_pll_inst_from_pin(pad_name)
            except:
                self.logger.error("Cannot find a pll with {} as input".format(pad_name))
                quit()

            block["input_clock"]     = "EXTERNAL" if not lvds_input else "LVDS_RX"
            block["input_clock_pad"] = pin_name
            block["input_refclk_name"] = refclk_name
            block["resource"]        = pll_res
            block["clock_no"]        = clock_no
            self.logger.info("Clock source: {}, using EXT_CLK{}".format(block["input_clock"], clock_no))
            self.platform.get_pll_resource(pll_res)
        else:
            block["input_clock"]  = "INTERNAL" if self.type == "TITANIUMPLL" else "CORE"
            block["resource"]     = self.platform.get_free_pll_resource()
            block["input_signal"] = name
            self.logger.info("Clock source: {}".format(block["input_clock"]))

        self.logger.info("PLL used     : " + colorer(str(self.platform.pll_used), "cyan"))
        self.logger.info("PLL available: " + colorer(str(self.platform.pll_available), "cyan"))

        block["input_freq"] = freq

        self.logger.info("Use {}".format(colorer(block["resource"], "green")))

    def create_clkout(self, cd, freq, phase=0, margin=0, name="", with_reset=True, dyn_phase=False, is_feedback=False):
        assert self.nclkouts < self.nclkouts_max

        clk_out_name = f"{self.name}_clkout{self.nclkouts}" if name == "" else name

        if cd is not None:
            self.platform.add_extension([(clk_out_name, 0, Pins(1))])
            clk_name = f"{cd.name}_clk"
            clk_out = self.platform.request(clk_out_name)
            self.comb += cd.clk.eq(clk_out)
            self.platform.add_period_constraint(clk=clk_out, period=1e9/freq, name=clk_name)
            if with_reset:
                self.specials += AsyncResetSynchronizer(cd, ~self.locked)
            self.platform.toolchain.excluded_ios.append(clk_out_name)

        create_clkout_log(self.logger, clk_out_name, freq, margin, self.nclkouts)

        block = self.platform.toolchain.ifacewriter.get_block(self.name)

        if is_feedback:
            assert block["feedback"] == -1
            block["feedback"] = self.nclkouts

        self.nclkouts += 1

        block["clk_out"].append([clk_out_name, freq, phase, margin, dyn_phase])

    def extra(self, extra):
        block = self.platform.toolchain.ifacewriter.get_block(self.name)
        block["extra"] = extra

    def compute_config(self):
        import math

        block = self.platform.toolchain.ifacewriter.get_block(self.name)
        if block["feedback"] == -1:
            return
        clks_out = {}
        for clk_id, clk in enumerate(block["clk_out"]):
            clks_out[clk_id] = {"freq": clk[1], "phase": clk[2]}

        n_out       = self.nclkouts
        clk_in_freq = block["input_freq"]
        clk_fb_id   = block["feedback"]
        device      = self.platform.device

        vco_range   = self.get_vco_freq_range(device)
        pfd_range   = self.get_pfd_freq_range(device)
        pll_range   = self.get_pll_freq_range(device)

        if n_out > 1:
            O_fact = [2, 4, 8]
        else:
            O_fact = [1, 2, 4, 8]

        # Pre-Divider (N).
        # -----------------
        # F_PFD is between 10e6 and 100e6
        # so limit search to only acceptable factors
        N_min = int(math.ceil(clk_in_freq / pfd_range[1]))
        N_max = int(math.floor(clk_in_freq / pfd_range[0]))
        ## limit
        ### when fin is below FPLL_MAX min is < 1
        if N_min < 1:
            N_min = 1
        ### when fin is above FPLL_MIN and/or near max possible freq max is > 15
        if N_max > 15:
            N_max = 15

        # Multiplier (M).
        # ---------------
        ## 1. needs to know all ffbk * o * cfbk acceptable to max FVCO range
        oc_range     = []
        oc_min       = 256*8
        oc_max       = 0
        clk_fb_freq  = clks_out[clk_fb_id]["freq"]
        clk_fb_phase = clks_out[clk_fb_id]["phase"]

        c_range = self.get_c_range(device, clk_fb_phase)
        # FIXME: c_range must be limited to min/max
        for c in c_range: # 1. iterate around C factor and check fPLL
            if clk_fb_freq * c < pll_range[0] or clk_fb_freq > pll_range[1]:
                continue
            for o in O_fact:
                oc = o * c
                fvco_tmp = clk_fb_freq * oc
                if fvco_tmp >= vco_range[0] and fvco_tmp <= vco_range[1]:
                    oc_range.append([o, c])
                    # again get range
                    if oc > oc_max:
                        oc_max = oc
                    if oc < oc_min:
                        oc_min = oc

        ## 2. compute FVCO equation with informations already obtained
        ##    ie try all possible Fpfd freqs and try to find M with FVCO respect
        ##    when params are valid try to find Cx for each clock output enabled
        params_list = []
        for n in range(N_min, N_max + 1):
            fpfd_tmp = clk_in_freq / n
            # limit range using FVCO_MAX & FVCO_MIN
            # fVCO = fPFD * M * O * Cfbk
            # so:
            #          fVCO
            # M = ---------------
            #     fPFD * O * Cfbf
            #
            M_min = int(math.ceil(vco_range[0] / (fpfd_tmp * oc_max)))
            M_max = int(math.floor(vco_range[1] / (fpfd_tmp * oc_min)))
            if M_min < 1:
                M_min = 1
            if M_max > 255:
                M_max = 255
            for m in range(M_min, M_max + 1):
                for oc in oc_range:
                    [o, c] = oc
                    fvco_tmp = fpfd_tmp * m * o * c
                    if fvco_tmp >= vco_range[0] and fvco_tmp <= vco_range[1]:
                        # m * o * c must be below 256
                        if m * o * c > 255:
                            continue

                        fpll_tmp = fvco_tmp / o
                        cx_list = []
                        for clk_id, clk_cfg in clks_out.items():
                            found = False
                            c_div  = self.get_c_range(device, clk_cfg["phase"])
                            c_list = []
                            for cx in c_div:
                                if clk_id == clk_fb_id and cx != c:
                                    continue
                                clk_out = fpll_tmp / cx
                                # if a C is found: no need to search more
                                if clk_out == clk_cfg["freq"]:
                                    cx_list.append(cx)
                                    found = True
                                    break
                            # no solution found for this clk: params are uncompatibles
                            if found == False:
                                break
                        if len(cx_list) == n_out:
                            params_list.append([n, m, o, c, cx_list])
        vco_max_freq = 0
        o_div_max    = 0
        params_list2 = []
        for p in params_list:
            (n, m, o, c, cx_list) = p
            fpfd_tmp             = clk_in_freq / n
            fvco_tmp             = fpfd_tmp * m * o * c
            # Interface designer always select high VCO freq
            if fvco_tmp > vco_max_freq:
                vco_max_freq = fvco_tmp
                params_list2.clear()
                o_div_max = 0
            fpll_tmp = fvco_tmp / o
            if fvco_tmp == vco_max_freq:
                if o > o_div_max:
                    o_div_max = o
                params_list2.append({
                    "fvco" : fvco_tmp,
                    "fpll" : fpll_tmp,
                    "fpfd" : fpfd_tmp,
                    "M"    : m,
                    "N"    : n,
                    "O"    : o,
                    "Cfbk" : c,
                     **{f"c{n}" : cx_list[n] for n in range(n_out)},
                })

        # Again: Interface Designer prefers high O divider.
        # -------------------------------------------------
        final_list = []
        for p in params_list2:
            if p["O"] == o_div_max:
                final_list.append(p)

        assert len(final_list) != 0

        # Select first parameters set.
        # ----------------------------
        final_list = final_list[0]

        # Fill block with PLL configuration parameters.
        # ---------------------------------------------
        block["M"]        = final_list["M"]
        block["N"]        = final_list["N"]
        block["O"]        = final_list["O"]
        block["VCO_FREQ"] = final_list["fvco"]
        for i in range(self.nclkouts):
            block[f"CLKOUT{i}_DIV"] = final_list[f"c{i}"]

    def set_configuration(self):
        pass

    def do_finalize(self):
        # FIXME
        if not self.platform.family == "Trion":
            return

        # compute PLL configuration and arbitrary select first result
        self.compute_config()


# Efinix / TITANIUMPLL -----------------------------------------------------------------------------

class TITANIUMPLL(EFINIXPLL):
    nclkouts_max = 5
    def __init__(self, platform, dyn_phase_shift_pads=[]):
        EFINIXPLL.__init__(self, platform, version="V3", dyn_phase_shift_pads=dyn_phase_shift_pads)

# Efinix / TRION ----------------------------------------------------------------------------------

class TRIONPLL(EFINIXPLL):
    nclkouts_max = 3
    def __init__(self, platform):
        EFINIXPLL.__init__(self, platform, version="V1_V2")

    @staticmethod
    def get_vco_freq_range(device):
        FVCO_MIN = 500e6
        FVCO_MAX = 3600e6 # Local/Core, 1600 otherwise
        #FVCO_MIN = 1600e6
        return (FVCO_MIN, FVCO_MAX)

    @staticmethod
    def get_pfd_freq_range(device):
        FPFD_MIN = 10e6
        FPFD_MAX = 100e6
        return (FPFD_MIN, FPFD_MAX)

    @staticmethod
    def get_pll_freq_range(device):
        FPLL_MIN = 62.5e6
        FPLL_MAX = 1800e6 # when all C are < 64 else 1400
        return (FPLL_MIN, FPLL_MAX)

    @staticmethod
    def get_c_range(device, phase=0):
        if phase == 0:
            return [i for i in range(1, 257)]

        return {
             45: [4],
             90: [2, 4, 6],
            135: [4],
            180: [2],
            270: [2]
        }[phase]
