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


# GenericToolchain -------------------------------------------------------------------------

class GenericToolchain:
    attr_translate = {
        "keep": ("keep", "true"),
    }

    def __init__(self):
        self.clocks    = dict()
        self.false_paths = set() # FIXME: use it
        self.named_pc = []
        self.named_sc = []

    # method use to build timing params
    def build_timing_constr(self, vns, clocks):
        pass

    # method use to build project (if required)
    def build_timing_constr(self, vns, clocks):
        pass

    def _build(self, platform, fragment,
        build_dir      = "build",
        build_name     = "top",
        synth_opts     = "",
        run            = True,
        **kwargs):

        self._build_name = build_name
        self._synth_opts = synth_opts
        self.platform    = platform

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
        self.named_sc, self.named_pc = platform.resolve_signals(v_output.ns)
        v_file = build_name + ".v"
        v_output.write(v_file)
        platform.add_source(v_file)

        # Generate design io constraints file
        self.build_constr_file(self.named_sc, self.named_pc)

        # Generate design timing constraints file (in timing_constr file)
        self.build_timing_constr(v_output.ns, self.clocks)

        # Generate project
        self.build_project()

        # Generate build script
        script = self.build_script()

        # Run
        if run:
            self.run_script(script)

        os.chdir(cwd)

        return v_output.ns

    def add_period_constraint(self, platform, clk, period):
        clk.attr.add("keep")
        if clk in self.clocks:
            if period != self.clocks[clk]:
                raise ValueError("Clock already constrained to {:.2f}ns, new constraint to {:.2f}ns"
                    .format(self.clocks[clk], period))
        self.clocks[clk] = period
