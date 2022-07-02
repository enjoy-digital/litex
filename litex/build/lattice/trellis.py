#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018-2019 David Shah <dave@ds0.me>
# Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import sys
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.lattice import common
from litex.build.generic_toolchain import GenericToolchain

# LatticeTrellisToolchain --------------------------------------------------------------------------

class LatticeTrellisToolchain(GenericToolchain):
    attr_translate = {
        "keep": ("keep", "true"),
    }

    special_overrides = common.lattice_ecp5_trellis_special_overrides

    def __init__(self):
        super().__init__()
        self.yosys_template   = self._yosys_template
        self.build_template   = self._build_template

    def build(self, platform, fragment,
        nowidelut      = False,
        abc9           = False,
        timingstrict   = False,
        ignoreloops    = False,
        bootaddr       = 0,
        seed           = 1,
        spimode        = None,
        freq           = None,
        compress       = True,
        **kwargs):

        self._nowidelut    = nowidelut
        self._abc9         = abc9
        self._timingstrict = timingstrict
        self._ignoreloops  = ignoreloops
        self._bootaddr     = bootaddr
        self._seed         = seed
        self._spimode      = spimode
        self._freq         = freq
        self._compress     = compress

        return GenericToolchain.build(self, platform, fragment, **kwargs)

    # IO Constraints (.lpf) ------------------------------------------------------------------------

    @classmethod
    def _format_constraint(cls, c):
        if isinstance(c, Pins):
            return ("LOCATE COMP ", " SITE " + "\"" + c.identifiers[0] + "\"")
        elif isinstance(c, IOStandard):
            return ("IOBUF PORT ", " IO_TYPE=" + c.name)
        elif isinstance(c, Misc):
            return ("IOBUF PORT ", " " + c.misc)

    def _format_lpf(self, signame, pin, others, resname):
        fmt_c = [self._format_constraint(c) for c in ([Pins(pin)] + others)]
        lpf = []
        for pre, suf in fmt_c:
            lpf.append(pre + "\"" + signame + "\"" + suf + ";")
        return "\n".join(lpf)

    def build_io_constraints(self):
        lpf = []
        lpf.append("BLOCK RESETPATHS;")
        lpf.append("BLOCK ASYNCPATHS;")
        for sig, pins, others, resname in self.named_sc:
            if len(pins) > 1:
                for i, p in enumerate(pins):
                    lpf.append(self._format_lpf(sig + "[" + str(i) + "]", p, others, resname))
            else:
                lpf.append(self._format_lpf(sig, pins[0], others, resname))
        if self.named_pc:
            lpf.append("\n\n".join(self.named_pc))
        tools.write_to_file(self._build_name + ".lpf", "\n".join(lpf))

    # Yosys Helpers/Templates ----------------------------------------------------------------------

    _yosys_template = [
        "verilog_defaults -push",
        "verilog_defaults -add -defer",
        "{read_files}",
        "verilog_defaults -pop",
        "attrmap -tocase keep -imap keep=\"true\" keep=1 -imap keep=\"false\" keep=0 -remove keep=0",
        "synth_ecp5 {nwl} {abc} -json {build_name}.json -top {build_name}",
    ]

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

    # Project (.ys) --------------------------------------------------------------------------------

    def build_project(self):
        ys = []
        for l in self._yosys_template:
            ys.append(l.format(
                build_name = self._build_name,
                nwl        = "-nowidelut" if self._nowidelut else "",
                abc        = "-abc9" if self._abc9 else "",
                read_files = self._yosys_import_sources()
            ))
        tools.write_to_file(self._build_name + ".ys", "\n".join(ys))

    # NextPnr Helpers/Templates --------------------------------------------------------------------

    def nextpnr_ecp5_parse_device(self, device):
        device      = device.lower()
        family      = device.split("-")[0]
        size        = device.split("-")[1]
        speed_grade = device.split("-")[2][0]
        if speed_grade not in ["6", "7", "8"]:
           raise ValueError("Invalid speed grade {}".format(speed_grade))
        package     = device.split("-")[2][1:]
        if "256" in package:
            package = "CABGA256"
        elif "285" in package:
            package = "CSFBGA285"
        elif "381" in package:
            package = "CABGA381"
        elif "554" in package:
            package = "CABGA554"
        elif "756" in package:
            package = "CABGA756"
        else:
           raise ValueError("Invalid package {}".format(package))
        return (family, size, speed_grade, package)

    nextpnr_ecp5_architectures = {
        "lfe5u-12f"   : "12k",
        "lfe5u-25f"   : "25k",
        "lfe5u-45f"   : "45k",
        "lfe5u-85f"   : "85k",
        "lfe5um-25f"  : "um-25k",
        "lfe5um-45f"  : "um-45k",
        "lfe5um-85f"  : "um-85k",
        "lfe5um5g-25f": "um5g-25k",
        "lfe5um5g-45f": "um5g-45k",
        "lfe5um5g-85f": "um5g-85k",
    }

    # Script ---------------------------------------------------------------------------------------

    _build_template = [
        "yosys -l {build_name}.rpt {build_name}.ys",
        "nextpnr-ecp5 --json {build_name}.json --lpf {build_name}.lpf --textcfg {build_name}.config  \
    --{architecture} --package {package} --speed {speed_grade} {timefailarg} {ignoreloops} --seed {seed}",
        "ecppack {build_name}.config --svf {build_name}.svf --bit {build_name}.bit --bootaddr {bootaddr} {spimode} {freq} {compress}"
    ]

    def build_script(self):
        # Translate device to Nextpnr architecture/package
        (family, size, speed_grade, package) = self.nextpnr_ecp5_parse_device(self.platform.device)
        architecture = self.nextpnr_ecp5_architectures[(family + "-" + size)]

        if sys.platform in ("win32", "cygwin"):
            script_ext = ".bat"
            script_contents = "@echo off\nrem Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n\n"
            fail_stmt = " || exit /b"
        else:
            script_ext = ".sh"
            script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\nset -e\n"
            fail_stmt = ""

        # Validate options
        ecp5_mclk_freqs = [
            2.4,
            4.8,
            9.7,
            19.4,
            38.8,
            62.0,
        ]
        if self._freq is not None:
            assert self._freq in ecp5_mclk_freqs, "Invalid MCLK frequency. Valid frequencies: " + str(ecp5_mclk_freqs)

        for s in self._build_template:
            s_fail = s + "{fail_stmt}\n"  # Required so Windows scripts fail early.
            script_contents += s_fail.format(
                build_name      = self._build_name,
                architecture    = architecture,
                package         = package,
                speed_grade     = speed_grade,
                timefailarg     = "--timing-allow-fail" if not self._timingstrict else "",
                ignoreloops     = "--ignore-loops" if self._ignoreloops else "",
                bootaddr        = self._bootaddr,
                fail_stmt       = fail_stmt,
                seed            = self._seed,
                spimode         = "" if self._spimode is None else f"--spimode {self._spimode}",
                freq            = "" if self._freq is None else "--freq {}".format(self._freq),
                compress        = "" if not self._compress else "--compress")

        script_file = "build_" + self._build_name + script_ext
        tools.write_to_file(script_file, script_contents, force_unix=False)

        return script_file

    def run_script(self, script):
        if sys.platform in ("win32", "cygwin"):
            shell = ["cmd", "/c"]
        else:
            shell = ["bash"]

        if which("yosys") is None or which("nextpnr-ecp5") is None:
            msg = "Unable to find Yosys/Nextpnr toolchain, please:\n"
            msg += "- Add Yosys/Nextpnr toolchain to your $PATH."
            raise OSError(msg)

        if subprocess.call(shell + [script]) != 0:
            raise OSError("Error occured during Yosys/Nextpnr's script execution.")

    def add_period_constraint(self, platform, clk, period):
        platform.add_platform_command("""FREQUENCY PORT "{clk}" {freq} MHz;""".format(
            freq=str(float(1/period)*1000), clk="{clk}"), clk=clk)

def trellis_args(parser):
    toolchain_group = parser.add_argument_group(title="Toolchain options")
    toolchain_group.add_argument("--yosys-nowidelut",      action="store_true", help="Use Yosys's nowidelut mode.")
    toolchain_group.add_argument("--yosys-abc9",           action="store_true", help="Use Yosys's abc9 mode.")
    toolchain_group.add_argument("--nextpnr-timingstrict", action="store_true", help="Use strict Timing mode (Build will fail when Timings are not met).")
    toolchain_group.add_argument("--nextpnr-ignoreloops",  action="store_true", help="Ignore combinatorial loops in Timing Analysis.")
    toolchain_group.add_argument("--nextpnr-seed",         default=1, type=int, help="Set Nextpnr's seed.")
    toolchain_group.add_argument("--ecppack-bootaddr",     default=0,           help="Set boot address for next image.")
    toolchain_group.add_argument("--ecppack-spimode",      default=None,        help="Set slave SPI programming mode.")
    toolchain_group.add_argument("--ecppack-freq",         default=None,        help="Set SPI MCLK frequency.")
    toolchain_group.add_argument("--ecppack-compress",     action="store_true", help="Use Bitstream compression.")

def trellis_argdict(args):
    return {
        "nowidelut":    args.yosys_nowidelut,
        "abc9":         args.yosys_abc9,
        "timingstrict": args.nextpnr_timingstrict,
        "ignoreloops":  args.nextpnr_ignoreloops,
        "bootaddr":     args.ecppack_bootaddr,
        "spimode":      args.ecppack_spimode,
        "freq":         float(args.ecppack_freq) if args.ecppack_freq is not None else None,
        "compress":     args.ecppack_compress,
        "seed":         args.nextpnr_seed,
    }
