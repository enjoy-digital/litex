#
# This file is part of LiteX.
#
# Copyright (c) 2017-2018 William D. Jones <thor0505@comcast.net>
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause


import os
import sys
import subprocess
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.lattice import common
from litex.build.yosys_nextpnr_toolchain import YosysNextPNRToolchain, yosys_nextpnr_args, yosys_nextpnr_argdict

# LatticeIceStormToolchain -------------------------------------------------------------------------

class LatticeIceStormToolchain(YosysNextPNRToolchain):
    attr_translate = {
        "keep": ("keep", "true"),
    }
    supported_build_backend = ["litex", "edalize"]
    special_overrides = common.lattice_ice40_special_overrides

    family     = "ice40"
    synth_fmt  = "json"
    constr_fmt = "pcf"
    pnr_fmt    = "asc"
    packer_cmd = "icepack"

    def __init__(self):
        super().__init__()
        self._synth_opts  = "-dsp"
        self._pnr_opts    = ""
        self._packer_opts = "-s"

    def finalize(self):
        # Translate device to Nextpnr architecture/package
        (_, self._architecture, self._package) = self.parse_device()
        self._pnr_opts += f" --pre-pack {self._build_name}_pre_pack.py "
        self._packer_opts += f" {self._build_name}.asc {self._build_name}.bin"

        YosysNextPNRToolchain.finalize(self)

    # IO Constraints (.pcf) ------------------------------------------------------------------------

    def build_io_constraints(self):
        r = ""
        for sig, pins, others, resname in self.named_sc:
            if len(pins) > 1:
                for bit, pin in enumerate(pins):
                    r += "set_io {}[{}] {}\n".format(sig, bit, pin)
            else:
                r += "set_io {} {}\n".format(sig, pins[0])
        if self.named_pc:
            r += "\n" + "\n\n".join(self.named_pc)
        tools.write_to_file(self._build_name + ".pcf", r)
        return (self._build_name + ".pcf", "PCF")

    # Timing Constraints (in pre_pack file) --------------------------------------------------------

    def build_timing_constraints(self, vns):
        r = ""
        for clk, period in self.clocks.items():
            r += """ctx.addClock("{}", {})\n""".format(vns.get_name(clk), 1e3/period)
        tools.write_to_file(self._build_name + "_pre_pack.py", r)
        return (self._build_name + "_pre_pack.py", "PY")

    def parse_device(self):
        packages = {
            "lp384": ["qn32", "cm36", "cm49"],
            "lp1k": ["swg16tr", "cm36", "cm49", "cm81", "cb81", "qn84", "cm121", "cb121"],
            "hx1k": ["vq100", "cb132", "tq144"],
            "lp8k": ["cm81", "cm81:4k", "cm121", "cm121:4k", "cm225", "cm225:4k"],
            "hx8k": ["bg121", "bg121:4k", "cb132", "cb132:4k", "cm121",
                     "cm121:4k", "cm225", "cm225:4k", "cm81", "cm81:4k",
                     "ct256", "tq144:4k"],
            "up3k": ["sg48", "uwg30"],
            "up5k": ["sg48", "uwg30"],
            "u4k": ["sg48"],
        }

        (family, architecture, package) = self.platform.device.split("-")
        if family not in ["ice40"]:
            raise ValueError("Unknown device family {}".format(family))
        if architecture not in packages.keys():
            raise ValueError("Invalid device architecture {}".format(architecture))
        if package not in packages[architecture]:
            raise ValueError("Invalid device package {}".format(package))
        return (family, architecture, package)

    # Edalize tool name and tool options -----------------------------------------------------------
    def get_tool_options(self):
        tool_options = {
            "icepack_options": ["-s"],
            "yosys_synth_options": self._synth_opts.split(' '),
            "nextpnr_options": self.pnr_opts.split(' '),
        }
        return ("icestorm", {"tool_options": {"icestorm": tool_options}})


def icestorm_args(parser):
    toolchain_group = parser.add_argument_group(title="IceStorm toolchain options")
    yosys_nextpnr_args(toolchain_group)

def icestorm_argdict(args):
    return {
        **yosys_nextpnr_argdict(args),
    }
