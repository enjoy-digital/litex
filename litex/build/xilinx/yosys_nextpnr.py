#
# This file is part of LiteX.
#
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Victor Suarez Rovere <suarezvictor@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import sys
import math
from typing import NamedTuple, Union, List
import re
from shutil import which

from migen.fhdl.structure import _Fragment, wrap, Constant
from migen.fhdl.specials import Instance

from litex.build.generic_toolchain import GenericToolchain
from litex.build.generic_platform import *
from litex.build.xilinx.vivado import _xdc_separator, _format_xdc, _build_xdc
from litex.build import tools
from litex.build.xilinx import common


def _unwrap(value):
    return value.value if isinstance(value, Constant) else value

# Makefile -----------------------------------------------------------------------------------------

class _MakefileGenerator:
    class Var(NamedTuple):
        name: str
        value: Union[str, List[str]] = ""

    class Rule(NamedTuple):
        target: str
        prerequisites: List[str] = []
        commands: List[str] = []
        phony: bool = False

    def __init__(self, ast):
        self.ast = ast

    def generate(self):
        makefile = []
        for entry in self.ast:
            if isinstance(entry, str):
                makefile.append(entry)
            elif isinstance(entry, self.Var):
                if not entry.value:
                    makefile.append(f"{entry.name} :=")
                elif isinstance(entry.value, list):
                    indent = " " * (len(entry.name) + len(" := "))
                    line = f"{entry.name} := {entry.value[0]}"
                    for value in entry.value[1:]:
                        line += " \\"
                        makefile.append(line)
                        line = indent + value
                    makefile.append(line)
                elif isinstance(entry.value, str):
                    makefile.append(f"{entry.name} := {entry.value}")
                else:
                    raise
            elif isinstance(entry, self.Rule):
                makefile.append("")
                if entry.phony:
                    makefile.append(f".PHONY: {entry.target}")
                makefile.append(" ".join([f"{entry.target}:", *entry.prerequisites]))
                for cmd in entry.commands:
                    makefile.append(f"\t{cmd}")

        return "\n".join(makefile)


def _run_make():
    make_cmd = ["make", "-j1"]

    if which("nextpnr-xilinx") is None:
        msg = "Unable to find Yosys+Nextpnr toolchain, please:\n"
        msg += "- Add Yosys and Nextpnr tools to your $PATH."
        raise OSError(msg)

    if tools.subprocess_call_filtered(make_cmd, common.colors) != 0:
        raise OSError("Error occured during yosys or nextpnr script execution.")

# YosysNextpnrToolchain -------------------------------------------------------------------------------

class YosysNextpnrToolchain(GenericToolchain):
    attr_translate = {
        #"keep":            ("dont_touch", "true"),
        #"no_retiming":     ("dont_touch", "true"),
        #"async_reg":       ("async_reg",  "true"),
        #"mr_ff":           ("mr_ff",      "true"), # user-defined attribute
        #"ars_ff1":         ("ars_ff1",    "true"), # user-defined attribute
        #"ars_ff2":         ("ars_ff2",    "true"), # user-defined attribute
        #"no_shreg_extract": None
    }

    def __init__(self):
        super().__init__()
        self.f4pga_device = None
        self.bitstream_device = None
        self._partname = None

    def _check_properties(self):
        if not self.f4pga_device:
            try:
                self.f4pga_device = {
                    # FIXME: fine for now since only a few devices are supported, do more clever device re-mapping.
                    "xc7a35ticsg324-1L" : "xc7a35t",
                    "xc7a100tcsg324-1"  : "xc7a35t",
                    "xc7z010clg400-1"   : "xc7z010",
                    "xc7z020clg400-1"   : "xc7z020",
                }[self.platform.device]
            except KeyError:
                raise ValueError(f"f4pga_device is not specified")
        if not self.bitstream_device:
            try:
                # bitstream_device points to a directory in prjxray database
                # available bitstream_devices: artix7, kintex7, zynq7
                self.bitstream_device = {
                    "xc7a": "artix7", # xc7a35t, xc7a50t, xc7a100t, xc7a200t
                    "xc7z": "zynq7", # xc7z010, xc7z020
                }[self.platform.device[:4]]
            except KeyError:
                raise ValueError(f"Unsupported device: {self.platform.device}")
        # FIXME: prjxray-db doesn't have xc7a35ticsg324-1L - use closest replacement
        self._partname = {
            "xc7a35ticsg324-1L" : "xc7a35tcsg324-1",
            "xc7a100tcsg324-1"  : "xc7a100tcsg324-1",
            "xc7a200t-sbg484-1" : "xc7a200tsbg484-1",
            "xc7z010clg400-1"   : "xc7z010clg400-1",
            "xc7z020clg400-1"   : "xc7z020clg400-1",
        }.get(self.platform.device, self.platform.device)

    def build_script(self):
        Var = _MakefileGenerator.Var
        Rule = _MakefileGenerator.Rule

        makefile = _MakefileGenerator([
            "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n",
            Var("TOP", self._build_name),
            Var("PARTNAME", self._partname),
            Var("DEVICE", self.f4pga_device),
            Var("BITSTREAM_DEVICE", self.bitstream_device),
            "",
            Var("DB_DIR", "/usr/share/nextpnr/prjxray-db"), #FIXME: resolve path
            Var("CHIPDB_DIR", "/usr/share/nextpnr/xilinx-chipdb"), #FIXME: resolve path
            "",
            Var("VERILOG", [f for f,language,_ in self.platform.sources if language in ["verilog", "system_verilog"]]),
            Var("MEM_INIT", [f"{name}" for name in os.listdir() if name.endswith(".init")]),
            Var("SDC", f"{self._build_name}.sdc"),
            Var("XDC", f"{self._build_name}.xdc"),
            Var("ARTIFACTS", [
                    "$(TOP).fasm", "$(TOP).frames", 
                    "*.bit", "*.fasm", "*.json", "*.log", "*.rpt",
                    "constraints.place"
                ]),

            Rule("all", ["$(TOP).bit"], phony=True),
            Rule("$(TOP).json", ["$(VERILOG)", "$(MEM_INIT)", "$(XDC)"], commands=[
                    #"symbiflow_synth -t $(TOP) -v $(VERILOG) -d $(BITSTREAM_DEVICE) -p $(PARTNAME) -x $(XDC) > /dev/null"
                    #yosys -p "synth_xilinx -flatten -abc9 -nosrl -noclkbuf -nodsp -iopad -nowidelut" #forum: symbiflow_synth
                    'yosys -p "synth_xilinx -flatten -abc9 -nobram -arch xc7 -top $(TOP); write_json $(TOP).json" $(VERILOG) > /dev/null'
                ]),
            Rule("$(TOP).fasm", ["$(TOP).json"], commands=[
                    #"symbiflow_write_fasm -e $(TOP).eblif -d $(DEVICE) > /dev/null"
                    'nextpnr-xilinx --chipdb $(CHIPDB_DIR)/$(DEVICE).bin --xdc $(XDC) --json $(TOP).json --write $(TOP)_routed.json --fasm $(TOP).fasm > /dev/null'
                ]),
            Rule("$(TOP).frames", ["$(TOP).fasm"], commands=[
                    'fasm2frames.py --part $(PARTNAME) --db-root $(DB_DIR)/$(BITSTREAM_DEVICE) $(TOP).fasm > $(TOP).frames'
                ]),
            Rule("$(TOP).bit", ["$(TOP).frames"], commands=[
                    #"symbiflow_write_bitstream -d $(BITSTREAM_DEVICE) -f $(TOP).fasm -p $(PARTNAME) -b $(TOP).bit > /dev/null"
                    'xc7frames2bit --part_file $(DB_DIR)/$(BITSTREAM_DEVICE)/$(PARTNAME)/part.yaml --part_name $(PARTNAME) --frm_file $(TOP).frames --output_file $(TOP).bit > /dev/null'
                ]),
            Rule("clean", phony=True, commands=[
                    "rm -f $(ARTIFACTS)"
                ]),
        ])

        tools.write_to_file("Makefile", makefile.generate())
        return "Makefile"

    def build_timing_constraints(self, vns):
        self.platform.add_platform_command(_xdc_separator("Clock constraints"))
        #for clk, period in sorted(self.clocks.items(), key=lambda x: x[0].duid):
        #    platform.add_platform_command(
        #        "create_clock -period " + str(period) +
        #        " {clk}", clk=clk)
        pass #clock constraints not supported

    def build_io_constraints(self):
        tools.write_to_file(self._build_name + ".xdc", _build_xdc(self.named_sc, self.named_pc))
        return (self._build_name + ".xdc", "XDC")

    def _fix_instance(self, instance):
        pass

    def finalize(self):
        # toolchain-specific fixes
        for instance in self.fragment.specials:
            if isinstance(instance, Instance):
                self._fix_instance(instance)

    def build(self, platform, fragment,
        enable_xpm = False,
        **kwargs):

        #FIXME
        self.platform = platform
        self._check_properties()

        return GenericToolchain.build(self, platform, fragment, **kwargs)

    def add_false_path_constraint(self, platform, from_, to):
        # FIXME: false path constraints are currently not supported by the F4PGA toolchain
        return

def f4pga_build_args(parser):
    pass


def f4pga_build_argdict(args):
    return dict()
