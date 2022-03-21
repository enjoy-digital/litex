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

# Mixed Radiant+Yosys support

def _run_yosys(device, sources, vincpaths, build_name):
    ys_contents = ""
    incflags = ""
    for path in vincpaths:
        incflags += " -I" + path
    for filename, language, library, *copy in sources:
        assert language != "vhdl"
        ys_contents += "read_{}{} {}\n".format(language, incflags, filename)

    ys_contents += """\
hierarchy -top {build_name}

# Map keep to keep=1 for yosys
log
log XX. Converting (* keep = "xxxx" *) attribute for Yosys
log
attrmap -tocase keep -imap keep="true" keep=1 -imap keep="false" keep=0 -remove keep=0
select -list a:keep=1

# Add keep=1 for yosys to objects which have dont_touch="true" attribute.
log
log XX. Converting (* dont_touch = "true" *) attribute for Yosys
log
select -list a:dont_touch=true
setattr -set keep 1 a:dont_touch=true

# Convert (* async_reg = "true" *) to async registers for Yosys.
# (* async_reg = "true", dont_touch = "true" *) reg xilinxmultiregimpl0_regs1 = 1'd0;
log
log XX. Converting (* async_reg = "true" *) attribute to async registers for Yosys
log
select -list a:async_reg=true
setattr -set keep 1 a:async_reg=true

synth_nexus -top {build_name} -vm {build_name}_yosys.vm
""".format(build_name=build_name)

    ys_name = build_name + ".ys"
    tools.write_to_file(ys_name, ys_contents)

    if which("yosys") is None:
        msg = "Unable to find Yosys toolchain, please:\n"
        msg += "- Add Yosys toolchain to your $PATH."
        raise OSError(msg)

    if subprocess.call(["yosys", ys_name]) != 0:
        raise OSError("Subprocess failed")

# Constraints (.ldc) -------------------------------------------------------------------------------

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

# Project (.tcl) -----------------------------------------------------------------------------------

def _build_tcl(device, sources, vincpaths, build_name, pdc_file, synth_mode):
    tcl = []
    # Create project
    syn = "lse" if synth_mode == "lse" else "synplify"
    tcl.append(" ".join([
        "prj_create",
        "-name \"{}\"".format(build_name),
        "-impl \"impl\"",
        "-dev {}".format(device),
        "-synthesis \"" + syn + "\""
    ]))

    def tcl_path(path): return path.replace("\\", "/")

    # Add include paths
    vincpath = ";".join(map(lambda x: tcl_path(x), vincpaths))
    tcl.append("prj_set_impl_opt {include path} {\"" + vincpath + "\"}")

    # Add sources
    if synth_mode == "yosys":
        # NOTE: it is seemingly impossible to skip synthesis using the Tcl flow
        # so we give Synplify the structural netlist from Yosys which it won't actually touch
        # The other option is to call the low level Radiant commands starting from 'map'
        # with the structural netlist from Yosys, but this would be harder to do in a cross
        # platform way.
        tcl.append("prj_add_source \"{}_yosys.vm\" -work work".format(build_name))
        library = "work"
    else:
        for filename, language, library, *copy in sources:
            tcl.append("prj_add_source \"{}\" -work {}".format(tcl_path(filename), library))

    tcl.append("prj_add_source \"{}\" -work {}".format(tcl_path(pdc_file), library))

    # Set top level
    tcl.append("prj_set_impl_opt top \"{}\"".format(build_name))

    # Save project
    tcl.append("prj_save")

    # Build flow
    tcl.append("prj_run Synthesis -impl impl -forceOne")
    tcl.append("prj_run Map -impl impl")
    tcl.append("prj_run PAR -impl impl")
    tcl.append("prj_run Export -impl impl -task Bitgen")

    # Close project
    tcl.append("prj_close")

    tools.write_to_file(build_name + ".tcl", "\n".join(tcl))

# Script -------------------------------------------------------------------------------------------

def _build_script(build_name, device):
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

    script_contents += "{tool} {tcl_script}{fail_stmt}\n".format(
        tool = tool,
        tcl_script = build_name + ".tcl",
        fail_stmt  = fail_stmt)

    script_contents += "{copy_stmt} {radiant_product} {migen_product} {fail_stmt}\n".format(
        copy_stmt       = copy_stmt,
        fail_stmt       = fail_stmt,
        radiant_product = os.path.join("impl", build_name + "_impl.bit"),
        migen_product   = build_name + ".bit")

    build_script_file = "build_" + build_name + script_ext
    tools.write_to_file(build_script_file, script_contents, force_unix=False)
    return build_script_file

def _run_script(script):
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

    if subprocess.call(shell + [script]) != 0:
        raise OSError("Error occured during Radiant's script execution.")

def _check_timing(build_name):
    lines = open("impl/{}_impl.par".format(build_name), "r").readlines()
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

# LatticeRadiantToolchain --------------------------------------------------------------------------

class LatticeRadiantToolchain:
    attr_translate = {
        "keep":             ("syn_keep", "true"),
        "no_retiming":      ("syn_no_retiming", "true"),
    }

    special_overrides = common.lattice_NX_special_overrides

    def __init__(self):
        self.clocks      = {}
        self.false_paths = set() # FIXME: use it

    def build(self, platform, fragment,
        build_dir      = "build",
        build_name     = "top",
        run            = True,
        timingstrict   = True,
        synth_mode     = "radiant",
        **kwargs):

        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        # Finalize design
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        # Generate verilog
        v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
        named_sc, named_pc = platform.resolve_signals(v_output.ns)
        v_file = build_name + ".v"
        v_output.write(v_file)
        platform.add_source(v_file)

        # Generate design constraints file (.pdc)
        _build_pdc(named_sc, named_pc, self.clocks, v_output.ns, build_name)
        pdc_file = build_dir + "\\" + build_name + ".pdc"

        # Generate design script file (.tcl)
        _build_tcl(platform.device, platform.sources, platform.verilog_include_paths, build_name, pdc_file, synth_mode)

        # Generate build script
        script = _build_script(build_name, platform.device)

        # Run
        if run:
            if synth_mode == "yosys":
                _run_yosys(platform.device, platform.sources, platform.verilog_include_paths, build_name)
            _run_script(script)
            if timingstrict:
                _check_timing(build_name)

        os.chdir(cwd)

        return v_output.ns

    def add_period_constraint(self, platform, clk, period):
        clk.attr.add("keep")
        period = math.floor(period*1e3)/1e3 # round to lowest picosecond
        if clk in self.clocks:
            if period != self.clocks[clk]:
                raise ValueError("Clock already constrained to {:.2f}ns, new constraint to {:.2f}ns"
                    .format(self.clocks[clk], period))
        self.clocks[clk] = period

    def add_false_path_constraint(self, platform, from_, to):
        from_.attr.add("keep")
        to.attr.add("keep")
        if (to, from_) not in self.false_paths:
            self.false_paths.add((from_, to))

def radiant_build_args(parser):
    toolchain_group = parser.add_argument_group(title="Toolchain options")
    toolchain_group.add_argument("--synth-mode", default="synplify", help="Synthesis mode (synplify or yosys).")

def radiant_build_argdict(args):
    return {"synth_mode": args.synth_mode}
