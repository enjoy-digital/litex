#
# This file is part of LiteX.
#
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import math

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build.xilinx.vivado import _xdc_separator, _build_xdc
from litex.build import tools

try:
    from f4pga import Flow, make_flow_config
    from f4pga.common import set_verbosity_level
    from f4pga.cache import F4Cache
    from f4pga.flow_config import ProjectFlowConfig
except ModuleNotFoundError as e:
    raise ModuleNotFoundError("Try getting/updating F4PGA tool (https://github.com/chipsalliance/f4pga/)") from e

F4CACHEPATH = '.f4cache'


# F4PGAToolchain -------------------------------------------------------------------------------
# Formerly SymbiflowToolchain, Symbiflow has been renamed to F4PGA -----------------------------

class F4PGAToolchain:
    attr_translate = {
        "keep":            ("dont_touch", "true"),
        "no_retiming":     ("dont_touch", "true"),
        "async_reg":       ("async_reg",  "true"),
        "mr_ff":           ("mr_ff",      "true"), # user-defined attribute
        "ars_ff1":         ("ars_ff1",    "true"), # user-defined attribute
        "ars_ff2":         ("ars_ff2",    "true"), # user-defined attribute
        "no_shreg_extract": None
    }

    def __init__(self):
        self.clocks = dict()
        self.false_paths = set()
        self._partname = None

    def _generate_prj_flow(self, platform, build_name):
        target = "bitstream"

        prj_flow_cfg_dict = {}
        prj_flow_cfg_dict["dependencies"] = {}
        prj_flow_cfg_dict["values"] = {}
        prj_flow_cfg_dict[self._partname] = {}

        deps_cfg = prj_flow_cfg_dict["dependencies"]
        deps_cfg["sources"] = [f for f,language,_ in platform.sources if language in ["verilog", "system_verilog"]]
        deps_cfg["xdc"] = f"{build_name}.xdc"
        deps_cfg["sdc"] = f"{build_name}.sdc"
        deps_cfg["build_dir"] = os.getcwd()
        deps_cfg["synth_log"] = f"{build_name}_synth.log"
        deps_cfg["pack_log"] = f"{build_name}_pack.log"
        deps_cfg["json"] = f"{build_name}.json"

        values_cfg = prj_flow_cfg_dict["values"]
        values_cfg["top"] = build_name
        values_cfg["part_name"] = self._partname

        prj_flow_cfg = ProjectFlowConfig("")
        prj_flow_cfg.flow_cfg = prj_flow_cfg_dict

        flow_cfg = make_flow_config(prj_flow_cfg, self._partname)

        flow = Flow(
            target=target,
            cfg=flow_cfg,
            f4cache=F4Cache(F4CACHEPATH)
        )

        print("\nProject status:")
        flow.print_resolved_dependencies(0)
        print("")

        return flow

    def _build_clock_constraints(self, platform):
        platform.add_platform_command(_xdc_separator("Clock constraints"))
        for clk, period in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            platform.add_platform_command(
                "create_clock -period " + str(period) +
                " {clk}", clk=clk)

    def build(self, platform, fragment,
        build_dir  = "build",
        build_name = "top",
        run        = True,
        enable_xpm = False,
        **kwargs):

        # FIXME: prjxray-db doesn't have xc7a35ticsg324-1L and xc7a200t-sbg484-1
        # use closest replacement
        self._partname = {
            "xc7a35ticsg324-1L" : "xc7a35tcsg324-1",
            "xc7a200t-sbg484-1" : "xc7a200tsbg484-1",
        }.get(platform.device, platform.device)

        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        # Finalize design
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        # Generate timing constraints
        self._build_clock_constraints(platform)

        # Generate verilog
        v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
        named_sc, named_pc = platform.resolve_signals(v_output.ns)
        v_file = build_name + ".v"
        v_output.write(v_file)
        platform.add_source(v_file)

        set_verbosity_level(2)

        # Generate design constraints
        tools.write_to_file(build_name + ".xdc", _build_xdc(named_sc, named_pc))

        flow = self._generate_prj_flow(
            platform   = platform,
            build_name = build_name
        )

        if run:
            try:
                flow.execute()
            except Exception as e:
                print(e)

        flow.f4cache.save()

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
        # FIXME: false path constraints are currently not supported by the F4PGA toolchain
        return
