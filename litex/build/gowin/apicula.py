#
# This file is part of LiteX.
#
# Copyright (c) 2024 Mai Lapyst
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.gowin.gowin import _build_cst
from litex.build.yosys_nextpnr_toolchain import YosysNextPNRToolchain

class GowinApiculaToolchain(YosysNextPNRToolchain):
    family     = "gowin"
    synth_fmt  = "json"
    pnr_fmt    = "report"
    packer_cmd = "gowin_pack"

    def __init__(self):
        super().__init__()
        self.options = {}
        self.additional_cst_commands = []
        self._sys_clk_freq = None

    def build(self, platform, fragment, *args, **kwargs):
        self._sys_clk_freq = getattr(fragment, "sys_clk_freq", None)
        return YosysNextPNRToolchain.build(self, platform, fragment, *args, **kwargs)

    def _get_timing_target(self):
        frequencies = [1e3/period for period, _ in self.clocks.values()]
        if self._sys_clk_freq is not None:
            frequencies.append(self._sys_clk_freq/1e6)
        return max(frequencies, default=0)

    def build_io_constraints(self):
        _build_cst(self.named_sc, self.named_pc, self.additional_cst_commands, self._build_name)
        return (self._build_name + ".cst", "CST")

    def finalize(self):
        devicename = self.platform.devicename
        # Non-exhaustive list of family aliases that Gowin IDE supports but don't have a unique database
        if devicename == "GW1NR-9C":
            devicename = "GW1N-9C"
        elif devicename == "GW1NR-9":
            devicename = "GW1N-9"
        elif devicename == "GW1NSR-4C" or devicename == "GW1NSR-4":
            devicename = "GW1NS-4"
        elif devicename == "GW1NR-4C" or devicename == "GW1NR-4":
            devicename = "GW1N-4"
        elif devicename == "GW2AR-18C":
            devicename = "GW2A-18C"
        elif devicename == "GW2AR-18":
            devicename = "GW2A-18"

        # yosys doesn't know that some variant doesn't have lutram so we tell it
        if devicename in ["GW1NS-4"]:
            self._synth_opts += " -nolutram"

        pnr_opts = "--write {top}_routed.json --top {top} --device {device}" + \
            " --vopt family={devicename} --vopt cst={top}.cst"
        self._pnr_opts += pnr_opts.format(
            top        = self._build_name,
            device     = self.platform.device,
            devicename = devicename
        )

        # nextpnr's Gowin arch takes no SDC, so --freq is the only way to pass a
        # timing target; without it nextpnr defaults to 12 MHz. Include the SoC's
        # system frequency since PLL-generated clocks are not always constrained.
        max_freq = self._get_timing_target()
        if max_freq > 0:
            self._pnr_opts += f" --freq {round(max_freq, 3)}"

        self._packer_opts += "-d {devicename} -o {top}.fs {top}_routed.json".format(
            devicename = devicename,
            top        = self._build_name
        )

        # use_mspi_as_gpio and friends
        for option, value in self.options.items():
            if option.startswith("use_") and value:
                # Not all options are supported and may be just Gowin's software check
                if option not in ["use_mode_as_gpio"]:
                    self._packer_opts += " --" + option[4:]

        YosysNextPNRToolchain.finalize(self)
