#
# This file is part of LiteX.
#
# Copyright (c) 2020 David Corrigan <davidcorrigan714@gmail.com>
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
from litex.build import tools
from litex.build.lattice import common
from litex.build.generic_toolchain import GenericToolchain
from litex.build.yosys_wrapper import YosysWrapper

# Required by oxide too (FIXME)
def _format_constraint(c):
    if isinstance(c, Pins):
        return ("ldc_set_location -site {" + c.identifiers[0] + "} [get_ports ","]")
    elif isinstance(c, IOStandard):
        return ("ldc_set_port -iobuf {IO_TYPE="+c.name+"} [get_ports ", "]")
    elif isinstance(c, Misc):
        return ("ldc_set_port -iobuf {"+c.misc+"} [get_ports ", "]" )


def _format_ldc(signame, pin, others, resname):
    fmt_c = [_format_constraint(c) for c in ([Pins(pin)] + others) if not isinstance(c, Pins) or c.identifiers[0] != "X"]
    ldc = []
    for pre, suf in fmt_c:
        ldc.append(pre + signame + suf)
    return "\n".join(ldc)


def _build_pdc(named_sc, named_pc, clocks, vns, build_name):
    pdc = []

    for sig, pins, others, resname in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                pdc.append(_format_ldc("{" + sig + "[" + str(i) + "]}", p, others, resname))
        else:
            pdc.append(_format_ldc(sig, pins[0], others, resname))
    if named_pc:
        pdc.append("\n".join(named_pc))

    # Note: .pdc is only used post-synthesis, Synplify constraints clocks by default to 200MHz.
    for clk, period in clocks.items():
        clk_name = vns.get_name(clk)
        pdc.append("create_clock -period {} -name {} [{} {}];".format(
            str(period),
            clk_name,
            "get_ports" if clk_name in [name for name, _, _, _ in named_sc] else "get_nets",
            clk_name
            ))

    tools.write_to_file(build_name + ".pdc", "\n".join(pdc))


# LatticeRadiantToolchain --------------------------------------------------------------------------

class LatticeRadiantToolchain(GenericToolchain):
    attr_translate = {
        "keep":             ("syn_keep", "true"),
        "no_retiming":      ("syn_no_retiming", "true"),
    }

    special_overrides = common.lattice_NX_special_overrides

    def __init__(self):
        super().__init__()

        self._timingstrict = False
        self._synth_mode   = "radiant"
        self._yosys        = None

    def build(self, platform, fragment,
        timingstrict   = False,
        synth_mode     = "radiant",
        **kwargs):

        self._timingstrict = timingstrict
        self._synth_mode   = synth_mode

        return GenericToolchain.build(self, platform, fragment, **kwargs)

    # Mixed Radiant+Yosys support ------------------------------------------------------------------

    def finalize(self):
        if self._synth_mode != "yosys":
            return

        yosys_cmds = [
            "hierarchy -top {build_name}",
            "select -list a:keep=1",
            "# Add keep=1 for yosys to objects which have dont_touch=\"true\" attribute.",
            "log",
            "log XX. Converting (* dont_touch = \"true\" *) attribute for Yosys",
            "log",
            "select -list a:dont_touch=true",
            "setattr -set keep 1 a:dont_touch=true",
            "",
            "# Convert (* async_reg = \"true\" *) to async registers for Yosys.",
            "# (* async_reg = \"true\", dont_touch = \"true\" *) reg xilinxmultiregimpl0_regs1 = 1'd0;",
            "log",
            "log XX. Converting (* async_reg = \"true\" *) attribute to async registers for Yosys",
            "log",
            "select -list a:async_reg=true",
            "setattr -set keep 1 a:async_reg=true",
        ]

        self._yosys = YosysWrapper(self.platform, self._build_name,
                output_name=self._build_name+"_yosys", target="nexus",
                template=[], yosys_cmds=yosys_cmds,
                yosys_opts=self._synth_opts, synth_format="vm")

    # Constraints (.ldc) ---------------------------------------------------------------------------

    def build_io_constraints(self):
        _build_pdc(self.named_sc, self.named_pc, self.clocks, self._vns, self._build_name)
        return (self._build_name + ".pdc", "PDC")

    # Project (.tcl) -------------------------------------------------------------------------------

    def build_project(self):
        if self._synth_mode == "yosys":
            self._yosys.build_script()
        pdc_file = os.path.join(self._build_dir, self._build_name + ".pdc")
        tcl = []
        # Create project
        syn = "lse" if self._synth_mode == "lse" else "synplify"
        tcl.append(" ".join([
            "prj_create",
            "-name \"{}\"".format(self._build_name),
            "-impl \"impl\"",
            "-dev {}".format(self.platform.device),
            "-synthesis \"" + syn + "\""
        ]))

        def tcl_path(path): return path.replace("\\", "/")

        # Add include paths
        vincpath = ";".join(map(lambda x: tcl_path(x), self.platform.verilog_include_paths))
        tcl.append("prj_set_impl_opt {include path} {\"" + vincpath + "\"}")

        # Add sources
        if self._synth_mode == "yosys":
            # NOTE: it is seemingly impossible to skip synthesis using the Tcl flow
            # so we give Synplify the structural netlist from Yosys which it won't actually touch
            # The other option is to call the low level Radiant commands starting from 'map'
            # with the structural netlist from Yosys, but this would be harder to do in a cross
            # platform way.
            tcl.append("prj_add_source \"{}_yosys.vm\" -work work".format(self._build_name))
            library = "work"
        else:
            for filename, language, library, *copy in self.platform.sources:
                tcl.append("prj_add_source \"{}\" -work {}".format(tcl_path(filename), library))

        tcl.append("prj_add_source \"{}\" -work {}".format(tcl_path(pdc_file), library))

        # Set top level
        tcl.append("prj_set_impl_opt top \"{}\"".format(self._build_name))

        # Save project
        tcl.append("prj_save")

        # Build flow
        tcl.append("prj_run Synthesis -impl impl -forceOne")
        tcl.append("prj_run Map -impl impl")
        tcl.append("prj_run PAR -impl impl")
        tcl.append("prj_run Export -impl impl -task Bitgen")

        # Close project
        tcl.append("prj_close")

        tools.write_to_file(self._build_name + ".tcl", "\n".join(tcl))

    # Script ---------------------------------------------------------------------------------------

    def build_script(self):
        if sys.platform in ("win32", "cygwin"):
            tool = "pnmainc"
            script_ext = ".bat"
            script_contents = "@echo off\nrem Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n\n"
            copy_stmt = "copy"
            fail_stmt = " || exit /b"
        else:
            tool = "radiantc"
            script_ext = ".sh"
            script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\nset -e\n"
            copy_stmt = "cp"
            fail_stmt = ""

        if self._synth_mode == "yosys":
            script_contents += self._yosys.get_yosys_call(target="script") + "\n"

        script_contents += "{tool} {tcl_script}{fail_stmt}\n".format(
            tool = tool,
            tcl_script = self._build_name + ".tcl",
            fail_stmt  = fail_stmt)

        script_contents += "{copy_stmt} {radiant_product} {migen_product} {fail_stmt}\n".format(
            copy_stmt       = copy_stmt,
            fail_stmt       = fail_stmt,
            radiant_product = os.path.join("impl", self._build_name + "_impl.bit"),
            migen_product   = self._build_name + ".bit")

        build_script_file = "build_" + self._build_name + script_ext
        tools.write_to_file(build_script_file, script_contents, force_unix=False)
        return build_script_file

    def run_script(self, script):
        if sys.platform in ("win32", "cygwin"):
            shell = ["cmd", "/c"]
            tool  = "pnmainc"
        else:
            shell = ["bash"]
            tool  = "radiantc"

        if which(tool) is None:
            msg = "Unable to find Radiant toolchain, please:\n"
            msg += "- Add Radiant toolchain to your $PATH."
            raise OSError(msg)

        if self._synth_mode == "yosys" and which("yosys") is None:
            msg = "Unable to find Yosys toolchain, please:\n"
            msg += "- Add Yosys toolchain to your $PATH."
            raise OSError(msg)

        if subprocess.call(shell + [script]) != 0:
            raise OSError("Error occured during Radiant's script execution.")
        if self._timingstrict:
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
            # If there were no freq constraints in ldc, ratings will be dashed.
            # results will likely be terribly unreliable, so bail
            assert not setup == hold == "-", "No timing constraints were provided"
            setup, hold = map(float, (setup, hold))
            if setup > limit and hold > limit:
                # At least one run met timing
                # XXX is this necessarily the run from which outputs will be used?
                return
        raise Exception("Failed to meet timing")


def radiant_build_args(parser):
    toolchain_group = parser.add_argument_group(title="Radiant toolchain options")
    toolchain_group.add_argument("--synth-mode", default="synplify", help="Synthesis mode (synplify or yosys).")

def radiant_build_argdict(args):
    return {"synth_mode":   args.synth_mode}
