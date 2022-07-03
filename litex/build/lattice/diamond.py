#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017-2018 Sergiusz Bazanski <q3k@q3k.org>
# Copyright (c) 2017 William D. Jones <thor0505@comcast.net>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import sys
import math
import subprocess
import shutil
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.gen.fhdl.verilog import DummyAttrTranslate

from litex.build.generic_platform import *
from litex.build.generic_toolchain import GenericToolchain
from litex.build import tools
from litex.build.lattice import common


# LatticeDiamondToolchain --------------------------------------------------------------------------

class LatticeDiamondToolchain(GenericToolchain):
    attr_translate = {
        "keep":             ("syn_keep", "true"),
        "no_retiming":      ("syn_no_retiming", "true"),
    }

    special_overrides = common.lattice_ecp5_special_overrides

    def __init__(self):
        super().__init__()

    def build(self, platform, fragment,
        timingstrict   = False,
        **kwargs):

        self._timinstrict = timingstrict

        return GenericToolchain.build(self, platform, fragment, **kwargs)

    # Helpers --------------------------------------------------------------------------------------

    @classmethod
    def _produces_jedec(cls, device):
        return device.startswith("LCMX")

    # Constraints (.lpf) ---------------------------------------------------------------------------

    @classmethod
    def _format_constraint(cls, c):
        if isinstance(c, Pins):
            return ("LOCATE COMP ", " SITE " + "\"" + c.identifiers[0] + "\"")
        elif isinstance(c, IOStandard):
            return ("IOBUF PORT ", " IO_TYPE=" + c.name)
        elif isinstance(c, Misc):
            return ("IOBUF PORT ", " " + c.misc)

    @classmethod
    def _format_lpf(cls, signame, pin, others, resname):
        fmt_c = [cls._format_constraint(c) for c in ([Pins(pin)] + others)]
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
            lpf.append("\n".join(self.named_pc))

        # Note: .lpf is only used post-synthesis, Synplify constraints clocks by default to 200MHz.
        for clk, period in self.clocks.items():
            clk_name = self._vns.get_name(clk)
            lpf.append("FREQUENCY {} \"{}\" {} MHz;".format(
                "PORT" if clk_name in [name for name, _, _, _ in self.named_sc] else "NET",
                clk_name,
                str(1e3/period)))

        tools.write_to_file(self._build_name + ".lpf", "\n".join(lpf))

    # Project (.tcl) -------------------------------------------------------------------------------

    def build_project(self):
        tcl = []
        # Create project
        tcl.append(" ".join([
            "prj_project",
            "new -name \"{}\"".format(self._build_name),
            "-impl \"impl\"",
            "-dev {}".format(self.platform.device),
            "-synthesis \"synplify\""
        ]))

        def tcl_path(path): return path.replace("\\", "/")

        # Add include paths
        vincpath = ";".join(map(lambda x: tcl_path(x), self.platform.verilog_include_paths))
        tcl.append("prj_impl option {include path} {\"" + vincpath + "\"}")

        # Add sources
        for filename, language, library, *copy in self.platform.sources:
            tcl.append("prj_src add \"{}\" -work {}".format(tcl_path(filename), library))

        # Set top level
        tcl.append("prj_impl option top \"{}\"".format(self._build_name))

        # Save project
        tcl.append("prj_project save")

        # Build flow
        tcl.append("prj_run Synthesis -impl impl -forceOne")
        tcl.append("prj_run Translate -impl impl")
        tcl.append("prj_run Map -impl impl")
        tcl.append("prj_run PAR -impl impl")
        tcl.append("prj_run Export -impl impl -task Bitgen")
        if self._produces_jedec(self.platform.device):
            tcl.append("prj_run Export -impl impl -task Jedecgen")

        # Close project
        tcl.append("prj_project close")

        tools.write_to_file(self._build_name + ".tcl", "\n".join(tcl))

    # Script ---------------------------------------------------------------------------------------

    def build_script(self):
        on_windows = sys.platform in ("win32", "cygwin")
        if on_windows:
            script_ext = ".bat"
            script_contents = "@echo off\nrem Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n\n"
            copy_stmt = "copy"
            fail_stmt = " || exit /b"
        else:
            script_ext = ".sh"
            script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\nset -e\n"
            copy_stmt = "cp"
            fail_stmt = ""

        script_contents += "{tool} {tcl_script}{fail_stmt}\n".format(
            tool = "pnmainc" if on_windows else "diamondc",
            tcl_script = self._build_name + ".tcl",
            fail_stmt  = fail_stmt)
        for ext in (".bit", ".jed"):
            if ext == ".jed" and not self._produces_jedec(self.platform.device):
                continue
            script_contents += "{copy_stmt} {diamond_product} {migen_product} {fail_stmt}\n".format(
                copy_stmt       = copy_stmt,
                fail_stmt       = fail_stmt,
                diamond_product = os.path.join("impl", self._build_name + "_impl" + ext),
                migen_product   = self._build_name + ext)

        build_script_file = "build_" + self._build_name + script_ext
        tools.write_to_file(build_script_file, script_contents, force_unix=False)
        return build_script_file

    def run_script(self, script):
        on_windows = sys.platform in ("win32", "cygwin")
        if on_windows:
            shell = ["cmd", "/c"]
        else:
            shell = ["bash"]

        if which("pnmainc" if on_windows else "diamondc") is None:
            msg = "Unable to find Diamond toolchain, please:\n"
            msg += "- Add Diamond toolchain to your $PATH.\n"
            raise OSError(msg)

        if subprocess.call(shell + [script]) != 0:
            raise OSError("Error occured during Diamond's script execution.")

        if self.timingstrict:
            self._check_timing()

    def _check_timing(self):
        lines = open("impl/{}_impl.par".format(self._build_name), "r").readlines()
        runs = [None, None]
        for i in range(len(lines)-1):
            if lines[i].startswith("Level/") and lines[i+1].startswith("Cost "):
                runs[0] = i + 2
            if lines[i].startswith("* : Design saved.") and runs[0] is not None:
                runs[1] = i
                break
        assert all(map(lambda x: x is not None, runs))

        p = re.compile(r"(^\s*\S+\s+\*?\s+[0-9]+\s+)(\S+)(\s+\S+\s+)(\S+)(\s+.*)")
        for l in lines[runs[0]:runs[1]]:
            m = p.match(l)
            if m is None: continue
            limit = 1e-8
            setup = m.group(2)
            hold  = m.group(4)
            # If there were no freq constraints in lpf, ratings will be dashed.
            # results will likely be terribly unreliable, so bail
            assert not setup == hold == "-", "No timing constraints were provided"
            setup, hold = map(float, (setup, hold))
            if setup > limit and hold > limit:
                # At least one run met timing
                # XXX is this necessarily the run from which outputs will be used?
                return
        raise Exception("Failed to meet timing")
