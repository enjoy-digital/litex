#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import subprocess
import shutil

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.microsemi import common


# Helpers ------------------------------------------------------------------------------------------

def tcl_name(name):
    return "{" + name + "}"

# IO Constraints (.pdc) ----------------------------------------------------------------------------

def _format_io_constraint(c):
    if isinstance(c, Pins):
        return "-pin_name {} ".format(c.identifiers[0])
    elif isinstance(c, IOStandard):
        return "-io_std {} ".format(c.name)
    elif isinstance(c, Misc):
        return "-RES_PULL {} ".format(c.misc)
    else:
        raise NotImplementedError


def _format_io_pdc(signame, pin, others):
    fmt_c = [_format_io_constraint(c) for c in ([Pins(pin)] + others)]
    r = "set_io "
    r += "-port_name {} ".format(tcl_name(signame))
    for c in  ([Pins(pin)] + others):
        r += _format_io_constraint(c)
    r += "-fixed true "
    r += "\n"
    return r

def _build_io_pdc(named_sc, named_pc, build_name, additional_io_constraints):
    pdc = ""
    for sig, pins, others, resname in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                pdc += _format_io_pdc(sig + "[" + str(i) + "]", p, others)
        else:
            pdc += _format_io_pdc(sig, pins[0], others)
    pdc += "\n".join(additional_io_constraints)
    tools.write_to_file(build_name + "_io.pdc", pdc)

# Placement Constraints (.pdc) ---------------------------------------------------------------------

def _build_fp_pdc(build_name, additional_fp_constraints):
    pdc = "\n".join(additional_fp_constraints)
    tools.write_to_file(build_name + "_fp.pdc", pdc)

# Project (.tcl) -----------------------------------------------------------------------------------

def _build_tcl(platform, sources, build_dir, build_name):
    tcl = []

    # Create project
    tcl.append(" ".join([
        "new_project",
        "-location {./impl}",
        "-name {}".format(tcl_name(build_name)),
        "-project_description {}",
        "-block_mode 0",
        "-standalone_peripheral_initialization 0",
        "-instantiate_in_smartdesign 1",
        "-ondemand_build_dh 0",
        "-use_enhanced_constraint_flow 1",
        "-hdl {VERILOG}",
        "-family {PolarFire}",
        "-die {}",
        "-package {}",
        "-speed {}",
        "-die_voltage {}",
        "-part_range {}",
        "-adv_options {}"
        ]))

    die, package, speed = platform.device.split("-")
    tcl.append(" ".join([
        "set_device",
        "-family {PolarFire}",
        "-die {}".format(tcl_name(die)),
        "-package {}".format(tcl_name(package)),
        "-speed {}".format(tcl_name("-" + speed)),
        # FIXME: common to all PolarFire devices?
        "-die_voltage {1.0}",
        "-part_range {EXT}",
        "-adv_options {IO_DEFT_STD:LVCMOS 1.8V}",
        "-adv_options {RESTRICTPROBEPINS:1}",
        "-adv_options {RESTRICTSPIPINS:0}",
        "-adv_options {TEMPR:EXT}",
        "-adv_options {UNUSED_MSS_IO_RESISTOR_PULL:None}",
        "-adv_options {VCCI_1.2_VOLTR:EXT}",
        "-adv_options {VCCI_1.5_VOLTR:EXT}",
        "-adv_options {VCCI_1.8_VOLTR:EXT}",
        "-adv_options {VCCI_2.5_VOLTR:EXT}",
        "-adv_options {VCCI_3.3_VOLTR:EXT}",
        "-adv_options {VOLTR:EXT} "
    ]))

    # Add sources
    for filename, language, library, *copy in sources:
        filename_tcl = "{" + filename + "}"
        tcl.append("import_files -hdl_source " + filename_tcl)

    # Set top level
    tcl.append("set_root -module {}".format(tcl_name(build_name)))

    # Copy init files FIXME: support for include path on LiberoSoC?
    for file in os.listdir(build_dir):
        if file.endswith(".init"):
            tcl.append("file copy -- {} impl/synthesis".format(file))

    # Import io constraints
    tcl.append("import_files -io_pdc {}".format(tcl_name(build_name + "_io.pdc")))

    # Import floorplanner constraints
    tcl.append("import_files -fp_pdc {}".format(tcl_name(build_name + "_fp.pdc")))

    # Import timing constraints
    tcl.append("import_files -convert_EDN_to_HDL 0 -sdc {}".format(tcl_name(build_name + ".sdc")))

    # Associate constraints with tools
    tcl.append(" ".join(["organize_tool_files",
        "-tool {SYNTHESIZE}",
        "-file impl/constraint/{}.sdc".format(build_name),
        "-module {}".format(build_name),
        "-input_type {constraint}"
    ]))
    tcl.append(" ".join(["organize_tool_files",
        "-tool {PLACEROUTE}",
        "-file impl/constraint/io/{}_io.pdc".format(build_name),
        "-file impl/constraint/fp/{}_fp.pdc".format(build_name),
        "-file impl/constraint/{}.sdc".format(build_name),
        "-module {}".format(build_name),
        "-input_type {constraint}"
    ]))
    tcl.append(" ".join(["organize_tool_files",
        "-tool {VERIFYTIMING}",
        "-file impl/constraint/{}.sdc".format(build_name),
        "-module {}".format(build_name),
        "-input_type {constraint}"
    ]))

    # Build flow
    tcl.append("run_tool -name {CONSTRAINT_MANAGEMENT}")
    tcl.append("run_tool -name {SYNTHESIZE}")
    tcl.append("run_tool -name {PLACEROUTE}")
    tcl.append("run_tool -name {GENERATEPROGRAMMINGDATA}")
    tcl.append("run_tool -name {GENERATEPROGRAMMINGFILE}")

    # Generate tcl
    tools.write_to_file(build_name + ".tcl", "\n".join(tcl))

# Timing Constraints (.sdc) ------------------------------------------------------------------------

def _build_timing_sdc(vns, clocks, false_paths, build_name, additional_timing_constraints):
    sdc = []

    for clk, period in sorted(clocks.items(), key=lambda x: x[0].duid):
        sdc.append(
            "create_clock -name {clk} -period " + str(period) +
            " [get_nets {clk}]".format(clk=vns.get_name(clk)))
    for from_, to in sorted(false_paths,
                            key=lambda x: (x[0].duid, x[1].duid)):
        sdc.append(
            "set_clock_groups "
            "-group [get_clocks -include_generated_clocks -of [get_nets {from_}]] "
            "-group [get_clocks -include_generated_clocks -of [get_nets {to}]] "
            "-asynchronous".format(from_=from_, to=to))

    # generate sdc
    sdc += additional_timing_constraints
    tools.write_to_file(build_name + ".sdc", "\n".join(sdc))

# Script -------------------------------------------------------------------------------------------

def _build_script(build_name, device):
    if sys.platform in ("win32", "cygwin"):
        script_ext = ".bat"
        script_contents = "@echo off\nREM Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n\n"
        copy_stmt = "copy"
        fail_stmt = " || exit /b"
    else:
        script_ext = ".sh"
        script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n"
        copy_stmt = "cp"
        fail_stmt = " || exit 1"

    script_file = "build_" + build_name + script_ext
    tools.write_to_file(script_file, script_contents,
                        force_unix=False)
    return script_file

def _run_script(script):
    if sys.platform in ["win32", "cygwin"]:
        shell = ["cmd", "/c"]
    else:
        shell = ["bash"]

    if subprocess.call(shell + [script]) != 0:
        raise OSError("Subprocess failed")

# MicrosemiLiberoSoCPolarfireToolchain -------------------------------------------------------------

class MicrosemiLiberoSoCPolarfireToolchain:
    attr_translate = {}

    special_overrides = common.microsemi_polarfire_special_overrides

    def __init__(self):
        self.clocks      = dict()
        self.false_paths = set()
        self.additional_io_constraints     = []
        self.additional_fp_constraints     = []
        self.additional_timing_constraints = []

    def build(self, platform, fragment,
            build_dir      = "build",
            build_name     = "top",
            run            = False,
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
        top_file = build_name + ".v"
        v_output.write(top_file)
        platform.add_source(top_file)

        # Generate design script file (.tcl)
        _build_tcl(platform, platform.sources, build_dir, build_name)

        # Generate design io constraints file (.pdc)
        _build_io_pdc(named_sc, named_pc, build_name, self.additional_io_constraints)

        # Generate design placement constraints file (.pdc)
        _build_fp_pdc(build_name, self.additional_fp_constraints)

        # Generate design timing constraints file (.sdc)
        _build_timing_sdc(v_output.ns, self.clocks, self.false_paths, build_name,
            self.additional_timing_constraints)

        # Generate build script
        script = _build_script(build_name, platform.device)

        # Run
        if run:
            # Delete previous impl
            if os.path.exists("impl"):
                shutil.rmtree("impl")
            _run_script(script)

        os.chdir(cwd)

        return v_output.ns

    def add_period_constraint(self, platform, clk, period):
        if clk in self.clocks:
            if period != self.clocks[clk]:
                raise ValueError("Clock already constrained to {:.2f}ns, new constraint to {:.2f}ns"
                    .format(self.clocks[clk], period))
        self.clocks[clk] = period

    def add_false_path_constraint(self, platform, from_, to):
        if (to, from_) not in self.false_paths:
            self.false_paths.add((from_, to))
