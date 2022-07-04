#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
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

# OSFPGAToolchain -----------------------------------------------------------------------------------

class OSFPGAToolchain(GenericToolchain):
    attr_translate = {}

    def __init__(self, toolchain):
        super().__init__()
        self.toolchain = toolchain
        self.clocks    = dict()

    # Constraints ----------------------------------------------------------------------------------

    def build_io_constraints(self):
        return ("", "") # TODO

    # Timing Constraints (.sdc) --------------------------------------------------------------------

    def build_timing_constraints(self, vns):
        sdc = []
        for clk, period in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            sdc.append(f"create_clock -name {vns.get_name(clk)} -period {str(period)} [get_ports {{{vns.get_name(clk)}}}]")
        with open(f"{self._build_name}.sdc", "w") as f:
            f.write("\n".join(sdc))
        return (self._build_name + ".sdc", "SDC")

    # Project --------------------------------------------------------------------------------------

    def build_project(self):
        tcl = []

        # Create Design.
        tcl.append(f"create_design {self._build_name}")

        # Set Device.
        tcl.append(f"target_device {self.platform.device.upper()}")

        # Add Include Path.
        tcl.append("add_include_path ./")
        for include_path in self.platform.verilog_include_paths:
            tcl.append(f"add_include_path {include_path}")

        # Add Sources.
        for f, typ, lib in self.platform.sources:
            tcl.append(f"add_design_file {f}")

        # Set Top Module.
        tcl.append(f"set_top_module {self._build_name}")

        # Add Timings Constraints.
        tcl.append(f"add_constraint_file {self._build_name}.sdc")

        # Run.
        tcl.append("synth")
        tcl.append("packing")
        tcl.append("place")
        tcl.append("route")
        tcl.append("sta")
        tcl.append("power")
        tcl.append("bitstream")

        # Generate .tcl.
        with open("build.tcl", "w") as f:
            f.write("\n".join(tcl))

    # Script ---------------------------------------------------------------------------------------

    def build_script(self):
        return "" # unused

    def run_script(self, script):
        toolchain_sh = self.toolchain
        if which(toolchain_sh) is None:
            msg = f"Unable to find {toolchain_sh.upper()} toolchain, please:\n"
            msg += f"- Add {toolchain_sh.upper()} toolchain to your $PATH."
            raise OSError(msg)

        if subprocess.call([toolchain_sh, "--batch", "--script", "build.tcl"]) != 0:
            raise OSError(f"Error occured during {toolchain_sh.upper()}'s script execution.")
