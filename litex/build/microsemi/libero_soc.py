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
from litex.build.generic_toolchain import GenericToolchain
from litex.build.microsemi import common


# MicrosemiLiberoSoCPolarfireToolchain -------------------------------------------------------------

class MicrosemiLiberoSoCPolarfireToolchain(GenericToolchain):
    attr_translate = {}

    special_overrides = common.microsemi_polarfire_special_overrides

    def __init__(self):
        super().__init__()
        self.additional_io_constraints     = []
        self.additional_fp_constraints     = []
        self.additional_timing_constraints = []

    # Helpers --------------------------------------------------------------------------------------

    @classmethod
    def tcl_name(cls, name):
        return "{" + name + "}"

    # IO Constraints (.pdc) ------------------------------------------------------------------------

    @classmethod
    def _format_io_constraint(cls, c):
        if isinstance(c, Pins):
            return "-pin_name {} ".format(c.identifiers[0])
        elif isinstance(c, IOStandard):
            return "-io_std {} ".format(c.name)
        elif isinstance(c, Misc):
            return "-RES_PULL {} ".format(c.misc)
        else:
            raise NotImplementedError

    def _format_io_pdc(self, signame, pin, others):
        fmt_c = [self._format_io_constraint(c) for c in ([Pins(pin)] + others)]
        r = "set_io "
        r += "-port_name {} ".format(self.tcl_name(signame))
        for c in  ([Pins(pin)] + others):
            r += self._format_io_constraint(c)
        r += "-fixed true "
        r += "\n"
        return r

    def build_io_constraints(self):
        pdc = ""
        for sig, pins, others, resname in self.named_sc:
            if len(pins) > 1:
                for i, p in enumerate(pins):
                    pdc += self._format_io_pdc(sig + "[" + str(i) + "]", p, others)
            else:
                pdc += self._format_io_pdc(sig, pins[0], others)
        pdc += "\n".join(self.additional_io_constraints)
        tools.write_to_file(self._build_name + "_io.pdc", pdc)
        return (self._build_name + "_io.pdc", "PDC")

    # Placement Constraints (.pdc) -----------------------------------------------------------------

    def build_placement_constraints(self):
        pdc = "\n".join(self.additional_fp_constraints)
        tools.write_to_file(self._build_name + "_fp.pdc", pdc)
        return (self._build_name + "_fp.pdc", "PDC")

    # Project (.tcl) -------------------------------------------------------------------------------

    def build_project(self):
        tcl = []

        # Create project
        tcl.append(" ".join([
            "new_project",
            "-location {./impl}",
            "-name {}".format(self.tcl_name(self._build_name)),
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

        die, package, speed = self.platform.device.split("-")
        tcl.append(" ".join([
            "set_device",
            "-family {PolarFire}",
            "-die {}".format(self.tcl_name(die)),
            "-package {}".format(self.tcl_name(package)),
            "-speed {}".format(self.tcl_name("-" + speed)),
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
        for filename, language, library, *copy in self.platform.sources:
            filename_tcl = "{" + filename + "}"
            tcl.append("import_files -hdl_source " + filename_tcl)

        # Set top level
        tcl.append("set_root -module {}".format(self.tcl_name(self._build_name)))

        # Copy init files FIXME: support for include path on LiberoSoC?
        for file in os.listdir(self._build_dir):
            if file.endswith(".init"):
                tcl.append("file copy -- {} impl/synthesis".format(file))

        # Import io constraints
        tcl.append("import_files -io_pdc {}".format(self.tcl_name(self._build_name + "_io.pdc")))

        # Import floorplanner constraints
        tcl.append("import_files -fp_pdc {}".format(self.tcl_name(self._build_name + "_fp.pdc")))

        # Import timing constraints
        tcl.append("import_files -convert_EDN_to_HDL 0 -sdc {}".format(self.tcl_name(self._build_name + ".sdc")))

        # Associate constraints with tools
        tcl.append(" ".join(["organize_tool_files",
            "-tool {SYNTHESIZE}",
            "-file impl/constraint/{}.sdc".format(self._build_name),
            "-module {}".format(self._build_name),
            "-input_type {constraint}"
        ]))
        tcl.append(" ".join(["organize_tool_files",
            "-tool {PLACEROUTE}",
            "-file impl/constraint/io/{}_io.pdc".format(self._build_name),
            "-file impl/constraint/fp/{}_fp.pdc".format(self._build_name),
            "-file impl/constraint/{}.sdc".format(self._build_name),
            "-module {}".format(self._build_name),
            "-input_type {constraint}"
        ]))
        tcl.append(" ".join(["organize_tool_files",
            "-tool {VERIFYTIMING}",
            "-file impl/constraint/{}.sdc".format(self._build_name),
            "-module {}".format(self._build_name),
            "-input_type {constraint}"
        ]))

        # Build flow
        tcl.append("run_tool -name {CONSTRAINT_MANAGEMENT}")
        tcl.append("run_tool -name {SYNTHESIZE}")
        tcl.append("run_tool -name {PLACEROUTE}")
        tcl.append("run_tool -name {GENERATEPROGRAMMINGDATA}")
        tcl.append("run_tool -name {GENERATEPROGRAMMINGFILE}")

        # Generate tcl
        tools.write_to_file(self._build_name + ".tcl", "\n".join(tcl))
        return self._build_name + ".tcl"

    # Timing Constraints (.sdc) --------------------------------------------------------------------

    def build_timing_constraints(self, vns):
        sdc = []

        for clk, [period, name] in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            clk_sig = self._vns.get_name(clk)
            if name is None:
                name = clk_sig
            sdc.append(
                "create_clock -name {name} -period " + str(period) +
                " [get_nets {clk}]".format(name=name, clk=clk_sig))
        for from_, to in sorted(self.false_paths,
                                key=lambda x: (x[0].duid, x[1].duid)):
            sdc.append(
                "set_clock_groups "
                "-group [get_clocks -include_generated_clocks -of [get_nets {from_}]] "
                "-group [get_clocks -include_generated_clocks -of [get_nets {to}]] "
                "-asynchronous".format(from_=from_, to=to))

        # generate sdc
        sdc += self.additional_timing_constraints
        tools.write_to_file(self._build_name + ".sdc", "\n".join(sdc))
        return (self._build_name + ".sdc", "SDC")

    # Script ---------------------------------------------------------------------------------------

    def build_script(self):
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

        script_file = "build_" + self._build_name + script_ext
        tools.write_to_file(script_file, script_contents,
                            force_unix=False)
        return script_file

    def run_script(self, script):
        # Delete previous impl
        if os.path.exists("impl"):
            shutil.rmtree("impl")

        if sys.platform in ["win32", "cygwin"]:
            shell = ["cmd", "/c"]
        else:
            shell = ["bash"]

        if subprocess.call(shell + [script]) != 0:
            raise OSError("Subprocess failed")

    def add_false_path_constraint(self, platform, from_, to):
        if (to, from_) not in self.false_paths:
            self.false_paths.add((from_, to))
