#
# This file is part of LiteX.
#
# Copyright (c) 2020 Pepijn de Vos <pepijndevos@gmail.com>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import math
import subprocess
from shutil import which, copyfile

from migen.fhdl.structure import _Fragment

from litex.build.generic_toolchain import GenericToolchain
from litex.build.generic_platform import *
from litex.build import tools


# GowinToolchain -----------------------------------------------------------------------------------

class GowinToolchain(GenericToolchain):
    attr_translate = {}

    def __init__(self):
        super().__init__()
        self.options = {}

    def finalize(self):
        if self.platform.verilog_include_paths:
            self.options["include_path"] = "{" + ";".join(self.platform.verilog_include_paths) + "}"

        self.apply_hyperram_integration_hack(self._build_name + ".v")

    def apply_hyperram_integration_hack(self, v_file):
        # FIXME: Gowin EDA expects a very specific HypeRAM integration pattern, modify generated verilog to match it.

        # Convert to vectors.
        tools.replace_in_file(v_file, "O_hpram_reset_n", "O_hpram_reset_n[0]")
        tools.replace_in_file(v_file, "O_hpram_cs_n",    "O_hpram_cs_n[0]")
        tools.replace_in_file(v_file, "O_hpram_rwds",    "O_hpram_rwds[0]")
        tools.replace_in_file(v_file, "O_hpram_ck ",     "O_hpram_ck[0] ")
        tools.replace_in_file(v_file, "O_hpram_ck_n ",   "O_hpram_ck_n[0] ")
        tools.replace_in_file(v_file, "O_hpram_ck,",     "O_hpram_ck[0],")
        tools.replace_in_file(v_file, "O_hpram_ck_n,",   "O_hpram_ck_n[0],")
        tools.replace_in_file(v_file, "wire O_hpram_reset_n[0]", "wire [0:0] O_hpram_reset_n")
        tools.replace_in_file(v_file, "wire O_hpram_cs_n[0]",    "wire [0:0] O_hpram_cs_n")
        tools.replace_in_file(v_file, "wire IO_hpram_rwds[0]",   "wire [0:0] IO_hpram_rwds")
        tools.replace_in_file(v_file, "wire O_hpram_ck[0]",      "wire [0:0] O_hpram_ck")
        tools.replace_in_file(v_file, "wire O_hpram_ck_n[0]",    "wire [0:0] O_hpram_ck_n")

        # Apply Synthesis directives.
        tools.replace_in_file(v_file, "wire [0:0] IO_hpram_rwds,", "wire [0:0] IO_hpram_rwds, /* synthesis syn_tristate = 1 */")
        tools.replace_in_file(v_file, "wire [7:0] IO_hpram_dq,",    "wire [7:0] IO_hpram_dq,  /* synthesis syn_tristate = 1 */")
        tools.replace_in_file(v_file, "[1:0] IO_psram_rwds,", "[1:0] IO_psram_rwds, /* synthesis syn_tristate = 1 */")
        tools.replace_in_file(v_file, "[15:0] IO_psram_dq,",    "[15:0] IO_psram_dq,  /* synthesis syn_tristate = 1 */")

    # Constraints (.cst ) --------------------------------------------------------------------------

    def build_io_constraints(self):
        cst = []

        flat_sc = []
        for name, pins, other, resource in self.named_sc:
            if len(pins) > 1:
                for i, p in enumerate(pins):
                    flat_sc.append((f"{name}[{i}]", p, other))
            else:
                flat_sc.append((name, pins[0], other))

        for name, pin, other in flat_sc:
            if pin != "X":
                cst.append(f"IO_LOC \"{name}\" {pin};")

            for c in other:
                if isinstance(c, IOStandard):
                    cst.append(f"IO_PORT \"{name}\" IO_TYPE={c.name};")
                elif isinstance(c, Misc):
                    cst.append(f"IO_PORT \"{name}\" {c.misc};")

        if self.named_pc:
            cst.extend(self.named_pc)

        tools.write_to_file("top.cst", "\n".join(cst))
        return ("top.cst", "CST")

    # Timing Constraints (.sdc ) -------------------------------------------------------------------

    def build_timing_constraints(self, vns):
        sdc = []
        for clk, period in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            sdc.append(f"create_clock -name {vns.get_name(clk)} -period {str(period)} [get_ports {{{vns.get_name(clk)}}}]")
        tools.write_to_file("top.sdc", "\n".join(sdc))
        return ("top.sdc", "SDC")

    # Project (tcl) --------------------------------------------------------------------------------

    def build_project(self):
        tcl = []

        # Set Device.
        tcl.append(f"set_device -name {self.platform.devicename} {self.platform.device}")

        # Add IOs Constraints.
        tcl.append("add_file top.cst")

        # Add Timings Constraints.
        tcl.append("add_file top.sdc")

        # Add Sources.
        for f, typ, lib in self.platform.sources:
            # Support windows/powershell
            if sys.platform == "win32":
                f = f.replace("\\", "\\\\")
            tcl.append(f"add_file {f}")

        # Set Options.
        for opt, val in self.options.items():
            tcl.append(f"set_option -{opt} {val}")

        # Run.
        tcl.append("run all")

        # Generate .tcl.
        tools.write_to_file("run.tcl", "\n".join(tcl))

    # Script ---------------------------------------------------------------------------------------

    def build_script(self):
        return "" # gw_sh use

    def run_script(self, script):
        # Support Powershell/WSL platform
        # Some python distros for windows (e.g, oss-cad-suite)
        # which does not have 'os.uname' support, we should check 'sys.platform' firstly.
        gw_sh = "gw_sh"
        if sys.platform.find("linux") >= 0:
            if os.uname().release.find("WSL") > 0:
                gw_sh += ".exe"
        if which(gw_sh) is None:
            msg = "Unable to find Gowin toolchain, please:\n"
            msg += "- Add Gowin toolchain to your $PATH."
            raise OSError(msg)

        if subprocess.call([gw_sh, "run.tcl"]) != 0:
            raise OSError("Error occured during Gowin's script execution.")

        # Copy Bitstream to from impl to gateware directory.
        copyfile(
            os.path.join("impl", "pnr", "project.fs"),
            os.path.join(build_name + ".fs")
        )
