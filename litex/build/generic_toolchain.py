#
# This file is part of LiteX.
#
# Copyright (c) 2012-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import math

from migen.fhdl.structure import _Fragment

# Generic Toolchain --------------------------------------------------------------------------------

class GenericToolchain:
    attr_translate = {
        "keep": ("keep", "true"),
    }

    def __init__(self):
        self.clocks      = dict()
        self.false_paths = set() # FIXME: use it
        self.named_pc    = []
        self.named_sc    = []

    def build_io_constraints(self):
        raise NotImplementedError("GenericToolchain.build_io_constraints must be overloaded.")

    def build_placement_constraints(self):
        # FIXME: Switch to fixed parameter when determined?
        pass # Pass since optional.

    def build_timing_constraints(self, vns):
        # FIXME: Switch to fixed parameter when determined?
        pass # Pass since optional.

    def build_project(self):
        pass # Pass since optional.

    def build_script(self):
        raise NotImplementedError("GenericToolchain.build_script must be overloaded.")

    def _build(self, platform, fragment,
        build_dir      = "build",
        build_name     = "top",
        synth_opts     = "",
        run            = True,
        **kwargs):

        self._build_name = build_name
        self._synth_opts = synth_opts
        self.platform    = platform

        # Create Build Directory.
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        # Finalize Design.
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        # Generate Verilog.
        v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
        self.named_sc, self.named_pc = platform.resolve_signals(v_output.ns)
        v_file = build_name + ".v"
        v_output.write(v_file)
        platform.add_source(v_file)

        # Generate Design IO Constraints File.
        self.build_io_constraints()

        # Generate Design Timing Constraints File.
        self.build_timing_constraints(v_output.ns)

        # Generate project.
        self.build_project()

        # Generate build script.
        script = self.build_script()

        # Run.
        if run:
            self.run_script(script)

        os.chdir(cwd)

        return v_output.ns

    def add_period_constraint(self, platform, clk, period):
        clk.attr.add("keep")
        period = math.floor(period*1e3)/1e3 # Round to lowest picosecond.
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
