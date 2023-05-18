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

from litex.build.yosys_nextpnr_toolchain import YosysNextPNRToolchain
from litex.build.generic_platform import *
from litex.build.xilinx.vivado import _xdc_separator, _format_xdc, _build_xdc
from litex.build import tools
from litex.build.xilinx import common


def _unwrap(value):
    return value.value if isinstance(value, Constant) else value


# YosysNextpnrToolchain ----------------------------------------------------------------------------

class XilinxYosysNextpnrToolchain(YosysNextPNRToolchain):
    attr_translate = {}

    family     = "xilinx"
    synth_fmt  = "json"
    constr_fmt = "xdc"
    pnr_fmt    = "fasm"
    packer_cmd = "xc7frames2bit"

    def __init__(self):
        super().__init__()
        self.f4pga_device = None
        self.bitstream_device = None
        self._partname = None
        self._pre_packer_cmd = ["fasm2frames.py"]
        self._synth_opts = "-flatten -abc9 -nobram -arch xc7 "

    def _check_properties(self):
        if not self.f4pga_device:
            try:
                self.f4pga_device = {
                    # FIXME: fine for now since only a few devices are supported, do more clever device re-mapping.
                    "xc7a35ticsg324-1L" : "xc7a35t",
                    "xc7a100tcsg324-1"  : "xc7a100t",
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

        # pnr options
        self._pnr_opts += "--chipdb {chipdb_dir}/{device}.bin --write {top}_routed.json".format(
            top        = self._build_name,
            chipdb_dir = "/usr/share/nextpnr/xilinx-chipdb",
            device     = self.f4pga_device,
        )

        # pre packer options
        self._pre_packer_opts["fasm2frames.py"] = "--part {part} --db-root {db_root} {top}.fasm > {top}.frames".format(
            part    = self._partname,
            db_root = f"/usr/share/nextpnr/prjxray-db/{self.bitstream_device}",
            top     = self._build_name
        )
        # packer options
        self._packer_opts += "--part_file {db_dir}/{part}/part.yaml --part_name {part} --frm_file {top}.frames --output_file {top}.bit".format(
            db_dir = f"/usr/share/nextpnr/prjxray-db/{self.bitstream_device}",
            part   = self._partname,
            top    = self._build_name
        )

        return YosysNextPNRToolchain.finalize(self)

    def build(self, platform, fragment,
        enable_xpm = False,
        **kwargs):

        #FIXME
        self.platform = platform
        self._check_properties()

        return YosysNextPNRToolchain.build(self, platform, fragment, **kwargs)

    def add_false_path_constraint(self, platform, from_, to):
        # FIXME: false path constraints are currently not supported by the F4PGA toolchain
        return

def f4pga_build_args(parser):
    pass


def f4pga_build_argdict(args):
    return dict()
