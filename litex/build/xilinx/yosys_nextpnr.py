#
# This file is part of LiteX.
#
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Victor Suarez Rovere <suarezvictor@gmail.com>
# Copyright (c) 2023 Hans Baier <hansfbaier@gmail.com>
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
from litex.build.xilinx.vivado import _xdc_separator, _format_xdc, _build_xdc, signed_bitstream_script
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

    def __init__(self, toolchain):
        assert toolchain in ["yosys+nextpnr", "openxc7"]
        self.is_openxc7 = toolchain == "openxc7"
        super().__init__()
        self.dbpart = None
        self._xc7family = None
        self._clock_constraints = ""
        self.additional_xdc_commands = []
        self._pre_packer_cmd = ["fasm2frames" if self.is_openxc7 else "fasm2frames.py"]
        self._synth_opts = "-flatten -abc9 -arch xc7 "

    xc7_family_map = {
        "a": "artix7",
        "k": "kintex7",
        "s": "spartan7",
        "z": "zynq7"
    }

    @property
    def device(self):
        return  {
            "xc7a35ticsg324-1L": "xc7a35tcsg324-1",
            "xc7a200t-sbg484-1": "xc7a200tsbg484-1",
        }.get(self.platform.device, self.platform.device)

    def _check_properties(self):
        pattern = re.compile("xc7([aksz])([0-9]+)(.*)-([0-9])")
        g = pattern.search(self.platform.device)
        if not self.dbpart:
            self.dbpart = f"xc7{g.group(1)}{g.group(2)}{g.group(3)}"

        if not self._xc7family:
            fam = g.group(1)
            self._xc7family = self.xc7_family_map[fam]

    def build_timing_constraints(self, vns):
        max_freq = 0
        xdc      = []
        xdc.append(_xdc_separator("Clock constraints"))

        for clk, [period, name] in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            clk_sig = self._vns.get_name(clk)
            # Search for the highest frequency.
            freq = int(1e3 / period)
            if freq > max_freq:
                max_freq = freq
            if name is None:
                name = clk_sig
            xdc.append(
                "create_clock -name {name} -period " + str(period) +
                " [get_ports {clk}]".format(name=name, clk=clk_sig))

        # FIXME: NextPNRWrapper is constructed at finalize level, too early
        # to update self._pnr_opts. The solution is to update _nextpnr instance.
        self._nextpnr._pnr_opts += f" --freq {max_freq}"
        # generate sdc
        xdc += self.additional_xdc_commands
        self._clock_constraints = "\n".join(xdc)

    def build_io_constraints(self):
        tools.write_to_file(self._build_name + ".xdc", _build_xdc(self.named_sc, self.named_pc) + self._clock_constraints)
        return (self._build_name + ".xdc", "XDC")

    def _fix_instance(self, instance):
        pass

    def finalize(self):
        # toolchain-specific fixes
        for instance in self.fragment.specials:
            if isinstance(instance, Instance):
                self._fix_instance(instance)

        if self.is_openxc7:
            chipdb_dir = os.environ.get('CHIPDB')
            if chipdb_dir is None or chipdb_dir == "":
                print("Error: please specify the directory, where you store your nextpnr-xilinx chipdb files in the environment variable CHIPDB (directory may be empty)")
                exit(1)
        else:
            chipdb_dir = "/usr/share/nextpnr/xilinx-chipdb"

        chipdb = os.path.join(chipdb_dir, self.dbpart) + ".bin"
        if not os.path.exists(chipdb):
            if self.is_openxc7:
                print(f"Chip database file '{chipdb}' not found, generating...")
                pypy3 = os.environ.get('PYPY3')
                if pypy3 is None or pypy3 == "":
                    pypy3 = which("pypy3")
                    if pypy3 is None:
                        pypy3 = "python3"

                nextpnr_xilinx_python_dir = os.environ.get('NEXTPNR_XILINX_PYTHON_DIR')
                if nextpnr_xilinx_python_dir is None or nextpnr_xilinx_python_dir == "":
                    nextpnr_xilinx_python_dir = "/snap/openxc7/current/opt/nextpnr-xilinx/python"
                bba = self.dbpart + ".bba"
                bbaexport = [pypy3, os.path.join(nextpnr_xilinx_python_dir, "bbaexport.py"), "--device", self.device, "--bba", bba]
                print(str(bbaexport))
                subprocess.run(bbaexport)
                subprocess.run(["bbasm", "-l", bba, chipdb])
                os.remove(bba)
            else:
                print(f"Chip database file '{chipdb}' not found. Please check your toolchain installation!")
                exit(1)

        # pnr options
        self._pnr_opts += "--chipdb {chipdb} --write {top}_routed.json".format(
            top    = self._build_name,
            chipdb = chipdb
        )

        if self.is_openxc7:
            prjxray_db_dir = os.environ.get('PRJXRAY_DB_DIR')
            if prjxray_db_dir is None or prjxray_db_dir == "":
                prjxray_db_dir = '/snap/openxc7/current/opt/nextpnr-xilinx/external/prjxray-db/'
        else:
            prjxray_db_dir = "/usr/share/nextpnr/prjxray-db/"

        if not os.path.isdir(prjxray_db_dir):
            print(f"{prjxray_db_dir} does not exist on your system. \n" + \
                    "Do you have the openXC7 toolchain installed? \n" + \
                    "You can get it here: https://github.com/openXC7/toolchain-installer")
            exit(1)

        # pre packer options
        self._pre_packer_opts[self._pre_packer_cmd[0]] = "--part {part} --db-root {db_root} {top}.fasm > {top}.frames".format(
            part    = self.device,
            db_root = os.path.join(prjxray_db_dir, self._xc7family),
            top     = self._build_name
        )
        # packer options
        self._packer_opts += "--part_file {db_dir}/{part}/part.yaml --part_name {part} --frm_file {top}.frames --output_file {top}.bit".format(
            db_dir = os.path.join(prjxray_db_dir, self._xc7family),
            part   = self.device,
            top    = self._build_name
        )

        return YosysNextPNRToolchain.finalize(self)

    def build_script(self):
        build_filename = YosysNextPNRToolchain.build_script(self)
        # Zynq7000/ZynqMP specific (signed bitstream).
        if self.platform.device[0:4] in ["xc7z", "xczu"]:
            with open(build_filename, "a") as fd:
                script_contents = signed_bitstream_script(self.platform, self._build_name)
                fd.write(script_contents)

        return build_filename

    def build(self, platform, fragment,
        enable_xpm = False,
        **kwargs):

        self.platform = platform
        self._check_properties()

        return YosysNextPNRToolchain.build(self, platform, fragment, **kwargs)

    def add_false_path_constraint(self, platform, from_, to):
        # FIXME: false path constraints are currently not supported by the toolchain
        return
