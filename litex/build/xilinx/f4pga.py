#
# This file is part of LiteX.
#
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import math

from migen.fhdl.structure import _Fragment

from litex.build.generic_toolchain import GenericToolchain
from litex.build.generic_platform import *
from litex.build.xilinx.vivado import _xdc_separator, _build_xdc
from litex.build import tools

try:
    from f4pga.flows.flow import Flow
    from f4pga.flows.commands import make_flow_config
    from f4pga.flows.common import set_verbosity_level
    from f4pga.flows.cache import F4Cache
    from f4pga.flows.flow_config import ProjectFlowConfig
except ModuleNotFoundError as e:
    raise ModuleNotFoundError("Try getting/updating F4PGA tool (https://github.com/chipsalliance/f4pga/)") from e

F4CACHEPATH = '.f4cache'


# F4PGAToolchain -----------------------------------------------------------------------------------
# Formerly SymbiflowToolchain, Symbiflow has been renamed to F4PGA ---------------------------------

class F4PGAToolchain(GenericToolchain):
    attr_translate = {
        "keep":            ("dont_touch", "true"),
        "no_retiming":     ("dont_touch", "true"),
        "async_reg":       ("async_reg",  "true"),
        "mr_ff":           ("mr_ff",      "true"), # user-defined attribute
        "ars_ff1":         ("ars_ff1",    "true"), # user-defined attribute
        "ars_ff2":         ("ars_ff2",    "true"), # user-defined attribute
        "no_shreg_extract": None
    }
    supported_build_backend = ["litex", "edalize"]

    def __init__(self):
        super().__init__()
        self._partname = None
        self._flow = None

    def build(self, platform, fragment,
        enable_xpm = False,
        **kwargs):

        # FIXME: prjxray-db doesn't have xc7a35ticsg324-1L and xc7a200t-sbg484-1
        # use closest replacement
        self._partname = {
            "xc7a35ticsg324-1L" : "xc7a35tcsg324-1",
            "xc7a200t-sbg484-1" : "xc7a200tsbg484-1",
        }.get(platform.device, platform.device)

        set_verbosity_level(2)

        return GenericToolchain.build(self, platform, fragment, **kwargs)

    def build_io_constraints(self):
        # Generate design constraints
        tools.write_to_file(self._build_name + ".xdc", _build_xdc(self.named_sc, self.named_pc))
        return (self._build_name + ".xdc", "xdc")

    def build_timing_constraints(self, vns):
        self.platform.add_platform_command(_xdc_separator("Clock constraints"))
        for clk, [period, name] in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            self.platform.add_platform_command(
                "create_clock -period " + str(period) +
                " {clk}", clk=clk)
        return ("", "")

    def build_script(self):
        pass # Pass since unused (F4PGA uses static TCL script)

    def build_project(self):
        target = "bitstream"

        prj_flow_cfg_dict = {}
        prj_flow_cfg_dict["dependencies"] = {}
        prj_flow_cfg_dict["values"] = {}
        prj_flow_cfg_dict[self._partname] = {}

        deps_cfg = prj_flow_cfg_dict["dependencies"]
        deps_cfg["sources"] = [f for f,language,_ in self.platform.sources if language in ["verilog", "system_verilog"]]
        deps_cfg["xdc"] = f"{self._build_name}.xdc"
        deps_cfg["sdc"] = f"{self._build_name}.sdc"
        deps_cfg["build_dir"] = os.getcwd()
        deps_cfg["synth_log"] = f"{self._build_name}_synth.log"
        deps_cfg["pack_log"] = f"{self._build_name}_pack.log"
        deps_cfg["json"] = f"{self._build_name}.json"

        values_cfg = prj_flow_cfg_dict["values"]
        values_cfg["top"] = self._build_name
        values_cfg["part_name"] = self._partname

        prj_flow_cfg = ProjectFlowConfig("")
        prj_flow_cfg.flow_cfg = prj_flow_cfg_dict

        flow_cfg = make_flow_config(prj_flow_cfg, self._partname)

        self._flow = Flow(
            target=target,
            cfg=flow_cfg,
            f4cache=F4Cache(F4CACHEPATH)
        )

        print("\nProject status:")
        self._flow.print_resolved_dependencies(0)
        print("")

    def run_script(self, script):
        if os.getenv("F4PGA_INSTALL_DIR", False) == False:
            msg = "Unable to find F4PGA toolchain.\n"
            msg += "Please set F4PGA_INSTALL_DIR environment variable "
            msg += "to F4PGA's installation path.\n"
            raise OSError(msg)

        try:
            self._flow.execute()
        except Exception as e:
            print(e)

        self._flow.f4cache.save()

    def add_false_path_constraint(self, platform, from_, to):
        # FIXME: false path constraints are currently not supported by the F4PGA toolchain
        return

    # Edalize tool name and tool options -----------------------------------------------------------
    def get_tool_options(self):
        device_name = {
            "xc7a10": "xc7a100t_test",
            "xc7a20": "xc7a200t_test",
            "xc7z01": "xc7z010_test",
            "xc7z02": "xc7z020_test",
        }.get(self.platform.device[0:6], "xc7a50t_test")

        tool_options = {
                "arch"   : "xilinx",
                "chip"   : device_name,
                "device" : "artix7" if self.platform.device.startswith("xc7a") else "zynq",
                "part"   : self._partname,
        }
        return ("f4pga", {"flow_options": tool_options})
