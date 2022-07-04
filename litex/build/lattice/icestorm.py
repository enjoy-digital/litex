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
from litex.build.generic_toolchain import GenericToolchain

# LatticeIceStormToolchain -------------------------------------------------------------------------

class LatticeIceStormToolchain(GenericToolchain):
    attr_translate = {
        "keep": ("keep", "true"),
    }
    supported_backend = ["LiteX", "edalize"]
    special_overrides = common.lattice_ice40_special_overrides

    def __init__(self):
        super().__init__()
        self.yosys_template = self._yosys_template
        self.build_template = self._build_template
        self._synth_opts    = "-dsp "
        self._pnr_opts      = ""

    def build(self, platform, fragment,
        timingstrict   = False,
        ignoreloops    = False,
        seed           = 1,
        **kwargs):

        self.timingstrict = timingstrict
        self.ignoreloops  = ignoreloops
        self.seed         = seed

        return GenericToolchain.build(self, platform, fragment, **kwargs)

    def finalize(self):
        # Translate device to Nextpnr architecture/package
        (_, self.architecture, self.package) = self.parse_device()

        # NextPnr options
        self._pnr_opts += " --pre-pack {build_name}_pre_pack.py \
--{architecture} --package {package} {timefailarg} {ignoreloops} --seed {seed}".format(
                build_name   = self._build_name,
                architecture = self.architecture,
                package      = self.package,
                timefailarg  = "--timing-allow-fail " if not self.timingstrict else "",
                ignoreloops  = "--ignore-loops " if self.ignoreloops else "",
                seed         = self.seed)

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

    # Yosys/Nextpnr Helpers/Templates --------------------------------------------------------------

    def _yosys_import_sources(self):
        includes = ""
        reads = []
        for path in self.platform.verilog_include_paths:
            includes += " -I" + path
        for filename, language, library, *copy in self.platform.sources:
            # yosys has no such function read_systemverilog
            if language == "systemverilog":
                language = "verilog -sv"
            reads.append("read_{}{} {}".format(
                language, includes, filename))
        return "\n".join(reads)

    _yosys_template = [
        "verilog_defaults -push",
        "verilog_defaults -add -defer",
        "{read_files}",
        "verilog_defaults -pop",
        "attrmap -tocase keep -imap keep=\"true\" keep=1 -imap keep=\"false\" keep=0 -remove keep=0",
        "synth_ice40 {synth_opts} -json {build_name}.json -top {build_name}",
    ]

    # Project (.ys) --------------------------------------------------------------------------------

    def build_project(self):
        ys = []
        for l in self._yosys_template:
            ys.append(l.format(
                build_name = self._build_name,
                read_files = self._yosys_import_sources(),
                synth_opts = self._synth_opts
            ))
        tools.write_to_file(self._build_name + ".ys", "\n".join(ys))

    # Script ---------------------------------------------------------------------------------------

    _build_template = [
        "yosys -l {build_name}.rpt {build_name}.ys",
        "nextpnr-ice40 --json {build_name}.json --pcf {build_name}.pcf --asc {build_name}.txt {pnr_opts}",
        "icepack -s {build_name}.txt {build_name}.bin"
    ]

    def build_script(self):

        if sys.platform in ("win32", "cygwin"):
            script_ext = ".bat"
            script_contents = "@echo off\nrem Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n\n"
            fail_stmt = " || exit /b"
        else:
            script_ext = ".sh"
            script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\nset -e\n"
            fail_stmt = ""

        for s in self.build_template:
            s_fail = s + "{fail_stmt}\n"  # Required so Windows scripts fail early.
            script_contents += s_fail.format(
                build_name   = self._build_name,
                fail_stmt    = fail_stmt,
                pnr_opts     = self._pnr_opts)

        script_file = "build_" + self._build_name + script_ext
        tools.write_to_file(script_file, script_contents, force_unix=False)

        return script_file

    def run_script(self, script):
        if sys.platform in ("win32", "cygwin"):
            shell = ["cmd", "/c"]
        else:
            shell = ["bash"]

        if which("yosys") is None or which("nextpnr-ice40") is None:
            msg = "Unable to find Yosys/Nextpnr toolchain, please:\n"
            msg += "- Add Yosys/Nextpnr toolchain to your $PATH."
            raise OSError(msg)

        if subprocess.call(shell + [script]) != 0:
            raise OSError("Error occured during Yosys/Nextpnr's script execution.")

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
            "nextpnr_options": self._pnr_opts.split(' '),
        }
        return ("icestorm", tool_options)


def icestorm_args(parser):
    toolchain_group = parser.add_argument_group(title="Toolchain options")
    toolchain_group.add_argument("--nextpnr-timingstrict", action="store_true", help="Make the build fail when Timing is not met.")
    toolchain_group.add_argument("--nextpnr-ignoreloops",  action="store_true", help="Use strict Timing mode (Build will fail when Timings are not met).")
    toolchain_group.add_argument("--nextpnr-seed",         default=1, type=int, help="Set Nextpnr's seed.")

def icestorm_argdict(args):
    return {
        "timingstrict": args.nextpnr_timingstrict,
        "ignoreloops":  args.nextpnr_ignoreloops,
        "seed":         args.nextpnr_seed,
    }
