#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import subprocess
import shutil
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.generic_toolchain import GenericToolchain
from litex.build.microsemi import common


# MicrosemiLiberoSoCToolchain ----------------------------------------------------------------------

class MicrosemiLiberoSoCToolchain(GenericToolchain):
    attr_translate = {}

    special_overrides = common.microsemi_polarfire_special_overrides

    def __init__(self):
        super().__init__()
        self.die                           = None
        self.family                        = None
        self.package                       = None
        self._tool_version                 = 0.0
        self.additional_io_constraints     = []
        self.additional_fp_constraints     = []
        self.additional_timing_constraints = []

        # Detect Libero SoC presence and version
        libero_bin_dir = which("libero")
        if libero_bin_dir is None:
           msg = "Unable to find or source Libero SoC toolchain, please make sure libero has been installed corectly.\n"
           raise OSError(msg)

        libero_verinfo_dir = os.path.abspath(os.path.join(os.path.dirname(libero_bin_dir), "../adm/verinfo"))
        # read the first line.
        with open(libero_verinfo_dir, "r") as fd:
            raw_version        = fd.readline()
            # version format xx.yy.zz.aa: only keep xx.yy
            self._tool_version = float(".".join(raw_version.split(".")[0:2]))

    # Prepare family here because pdc differs between devices...
    def finalize(self):
        # Device Format: die-XYYYZ
        # where X in [-1, -2, None]
        # YYY package
        # Z None for COM, I for IND, T1 for TGrade1, T2 for TGrade2, M for MIL
        self.die, self.package = self.platform.device.split("-")

        if self.die.startswith("M2GL"):
            self.family = "IGLOO2"
        elif self.die.startswith("MPF"):
            self.family = "PolarFire"
        elif self.die.startswith("A3PE") or self.die.startswith("M1A3PE"):
            if self.die.endswith("L"):
                self.family = "ProASIC3L"
            else:
                self.family = "ProASIC3E"
        elif self.die.startswith("A3P") or self.die.startswith("M1A3P") or self.die.startswith("M7A3P"):
            if self.die.endswith("L"):
                self.family = "ProASIC3L"
            else:
                self.family = "ProASIC3"
        else:
            raise error(f"unknown family for die: {self.die}")

        # proASCI3 support has been dropped after Release 11.9
        if self.family.startswith("ProASIC3"):
            assert self._tool_version <= 11.9


    # Helpers --------------------------------------------------------------------------------------

    @classmethod
    def tcl_name(cls, name):
        return "{" + name + "}"

    # IO Constraints (.pdc) ------------------------------------------------------------------------

    def _format_io_constraint(self, c):
        if isinstance(c, Pins):
            if self.family in ["PolarFire"]:
                return "-pin_name {} ".format(c.identifiers[0])
            else:
                return "-pinname {} ".format(c.identifiers[0])
        elif isinstance(c, IOStandard):
            if self.family in ["PolarFire"]:
                return "-io_std {} ".format(c.name)
            else:
                return "-iostd {} ".format(c.name)
        elif isinstance(c, Misc):
            return "-RES_PULL {} ".format(c.misc)
        else:
            raise NotImplementedError

    def _format_io_pdc(self, signame, pin, others):
        fmt_c = [self._format_io_constraint(c) for c in ([Pins(pin)] + others)]
        r = "set_io "
        if self.family in ["PolarFire"]:
            r += "-port_name {} ".format(self.tcl_name(signame))
        else:
            r += f"{signame} "
        for c in  ([Pins(pin)] + others):
            r += self._format_io_constraint(c)
        r += "-fixed {} ".format({True: "true", False: "yes"}[self.family in ["PolarFire"]])
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

        # when package starts with 1/2 it's the speed grade
        # otherwise speed grade is STD
        if self.package[0].isdecimal():
            speed        = "-" + self.package[0]
            self.package = self.package[1:]
        else:
            speed = "STD"

        # when package ends with a non decimal char it's the range
        if self.package.endswith("I"):
            part_range = "IND"
        elif self.package.endswith("T1"):
            part_range = "TGrade1"
        elif self.package.endswith("T2"):
            part_range = "TGrade2"
        elif self.package.endswith("M"):
            part_range = "MIL"
        else:
            part_range = "COM"
        if part_range in ["TGrade1", "TGrade2"]:
            self.package = self.package[:-2]
        elif part_range not in ["COM"]:
            self.package = self.package[:-1]

        voltage = "1.0"
        if self.family == "IGLOO2":
            voltage = "1.2"
        elif self.family.startswith("ProASIC3"): # ProASIC3L may be 1.2~1.5, 1.2, 1.5
            voltage = "1.5"

        # Create project
        create_proj_instr = [
            "new_project",
            "-location {./impl}",
            "-name {}".format(self.tcl_name(self._build_name)),
            "-project_description {}",
            "-block_mode 0",
            "-standalone_peripheral_initialization 0",
            "-instantiate_in_smartdesign 1",
            "-use_enhanced_constraint_flow 1",
            "-hdl {VERILOG}",
            "-family {}".format(self.tcl_name(self.family)),
            "-die {}".format(self.tcl_name(self.die)),
            "-package {}".format(self.tcl_name(self.package)),
            "-speed {}".format(self.tcl_name(speed)),
            "-die_voltage {}".format(self.tcl_name(voltage)),
            "-part_range {}".format(self.tcl_name(part_range)),
            "-adv_options {{TEMPR:{}}}".format(part_range),
            "-adv_options {VCCI_1.5_VOLTR:COM}",
            "-adv_options {VCCI_1.8_VOLTR:COM}",
            "-adv_options {VCCI_2.5_VOLTR:COM}",
            "-adv_options {VCCI_3.3_VOLTR:COM}",
            "-adv_options {{VOLTR:{}}}".format(part_range),
        ]
        if not self.family.startswith("ProASIC3"):
            create_proj_instr.append("-adv_options {VCCI_1.2_VOLTR:COM}")

        if self._tool_version > 11.9:
            create_proj_instr.append("-ondemand_build_dh 0")

        tcl.append(" ".join(create_proj_instr))

        # Add include path (required by readmemxx).
        if self._tool_version > 11.9:
            tcl.append(f"set_global_include_path_order -paths {{\"{os.getcwd()}\"}}")
        else:
            # Copy init files.
            for file in os.listdir(self._build_dir):
                if file.endswith(".init"):
                    tcl.append("file copy -- {} impl/synthesis".format(file))


        # Add sources
        for filename, language, library, *copy in self.platform.sources:
            filename_tcl = "{" + filename + "}"
            tcl.append("import_files -hdl_source " + filename_tcl)

        # Building the design Hierarchy (not supported by 11.9)
        if self._tool_version > 11.9:
            tcl.append("build_design_hierarchy")

        # Set top level
        tcl.append("set_root -module {}".format(self.tcl_name(self._build_name + "::work")))

        # Import io constraints
        tcl.append("import_files -{}pdc {}".format(
            {True: "", False: "io_"}[self.family.startswith("ProASIC3")],
            self.tcl_name(self._build_name + "_io.pdc")
        ))

        # Import floorplanner constraints
        if not self.family.startswith("ProASIC3"):
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
        if not self.family.startswith("ProASIC3"):
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
        if not self.family.startswith("ProASIC3"):
            tcl.append("run_tool -name {CONSTRAINT_MANAGEMENT}")
        tcl.append("run_tool -name {SYNTHESIZE}")
        tcl.append("run_tool -name {PLACEROUTE}")
        tcl.append("run_tool -name {GENERATEPROGRAMMINGDATA}")
        if self.family not in ["ProASIC3"]:
            tcl.append("run_tool -name {GENERATEPROGRAMMINGFILE}")
        
        # Export the FPExpress programming file to Libero SoC default location
        if not self.family.startswith("ProASIC3"):
            export_prog_job = [
                "export_prog_job",
                "-job_file_name {}".format(self.tcl_name(self._build_name)),
                "-export_dir {{./impl/designer/{}/export}}".format(self._build_name),
                "-bitstream_file_type {TRUSTED_FACILITY}",
                "-bitstream_file_components {{FABRIC {}}}".format({True: "SNVM", False: ""}[self.family in ["PolarFire"]]),
            ]

            if self.family in ["PolarFire"]:
                export_prog_job += [
                    "-zeroization_likenew_action 0",
                    "-zeroization_unrecoverable_action 0",
                    "-program_design 1",
                    "-program_spi_flash 0",
                    "-include_plaintext_passkey 0",
                    "-design_bitstream_format {PPD}",
                    "-prog_optional_procedures {}",
                    "-skip_recommended_procedures {}",
                    "-sanitize_snvm 0",
                ]
            
            tcl.append(" ".join(export_prog_job))

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

        script_contents += "libero script:" + self._build_name + ".tcl\n"
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
