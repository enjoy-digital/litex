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
from litex.build.yosys_nextpnr_toolchain import yosys_nextpnr_args, yosys_nextpnr_argdict
from litex.build.generic_platform import *
from litex.build.xilinx.vivado import _xdc_separator, _format_xdc, _build_xdc, signed_bitstream_script
from litex.build import tools
from litex.build.xilinx import common


def _unwrap(value):
    return value.value if isinstance(value, Constant) else value


_openxc7_default_prjxray_db_dir = "/snap/openxc7/current/opt/nextpnr-xilinx/external/prjxray-db/"
_openxc7_runtime_chipdb_dir     = "${CHIPDB:?Set CHIPDB to your nextpnr-xilinx chipdb directory}"
_openxc7_runtime_prjxray_db_dir = "${PRJXRAY_DB_DIR:-" + _openxc7_default_prjxray_db_dir + "}"


# YosysNextpnrToolchain ----------------------------------------------------------------------------

class XilinxYosysNextpnrToolchain(YosysNextPNRToolchain):
    attr_translate = {
        "keep": ("keep", "true"),
    }

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
        if g is None:
            raise OSError(f"Unsupported device {self.platform.device}")
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
            freq = 1e3 / period
            if freq > max_freq:
                max_freq = freq
            if name is None:
                name = clk_sig
            xdc.append("create_clock -name {name} -period {period} [get_ports {clk}]".format(
                name   = name,
                period = period,
                clk    = clk_sig))

        # FIXME: NextPNRWrapper is constructed at finalize level, too early
        # to update self._pnr_opts. The solution is to update _nextpnr instance.
        if max_freq > 0:
            self._nextpnr._pnr_opts += f" --freq {round(max_freq, 3)}"
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

        run = getattr(self, "_run", True)

        if self.is_openxc7:
            chipdb_dir = os.environ.get('CHIPDB')
            if run and (chipdb_dir is None or chipdb_dir == ""):
                raise OSError(
                    "Error: please specify the directory, where you store your "
                    "nextpnr-xilinx chipdb files in the environment variable "
                    "CHIPDB (directory may be empty)"
                )
            chipdb_arg_dir = chipdb_dir or _openxc7_runtime_chipdb_dir
        else:
            chipdb_dir = "/usr/share/nextpnr/xilinx-chipdb"
            chipdb_arg_dir = chipdb_dir

        chipdb     = os.path.join(chipdb_dir,     self.dbpart) + ".bin" if chipdb_dir else None
        chipdb_arg = os.path.join(chipdb_arg_dir, self.dbpart) + ".bin"
        if run and not os.path.exists(chipdb):
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
                bbaexport = [
                    pypy3,
                    os.path.join(nextpnr_xilinx_python_dir, "bbaexport.py"),
                    "--device", self.device,
                    "--bba",    bba,
                ]
                print(str(bbaexport))
                if subprocess.run(bbaexport).returncode != 0:
                    raise OSError(f"Error occured during bbaexport's execution for '{chipdb}'.")
                if subprocess.run(["bbasm", "-l", bba, chipdb]).returncode != 0:
                    raise OSError(f"Error occured during bbasm's execution for '{chipdb}'.")
                os.remove(bba)
            else:
                raise OSError(f"Chip database file '{chipdb}' not found. Please check your toolchain installation!")

        # pnr options
        self._pnr_opts += "--chipdb {chipdb} --write {top}_routed.json".format(
            top    = self._build_name,
            chipdb = chipdb_arg
        )

        if self.is_openxc7:
            prjxray_db_dir = os.environ.get('PRJXRAY_DB_DIR')
            if prjxray_db_dir is None or prjxray_db_dir == "":
                prjxray_db_dir = _openxc7_default_prjxray_db_dir
            prjxray_db_arg_dir = (
                os.environ.get('PRJXRAY_DB_DIR') or
                _openxc7_runtime_prjxray_db_dir
            )
        else:
            prjxray_db_dir = "/usr/share/nextpnr/prjxray-db/"
            prjxray_db_arg_dir = prjxray_db_dir

        if run and not os.path.isdir(prjxray_db_dir):
            raise OSError(f"{prjxray_db_dir} does not exist on your system. \n" + \
                    "Do you have the openXC7 toolchain installed? \n" + \
                    "You can get it here: https://github.com/openXC7/toolchain-installer")

        # pre packer options
        self._pre_packer_opts[self._pre_packer_cmd[0]] = (
            "--part {part} --db-root {db_root} "
            "{top}.fasm > {top}.frames"
        ).format(
            part    = self.device,
            db_root = os.path.join(prjxray_db_arg_dir, self._xc7family),
            top     = self._build_name
        )
        # packer options
        self._packer_opts += (
            "--part_file {db_dir}/{part}/part.yaml "
            "--part_name {part} "
            "--frm_file {top}.frames "
            "--output_file {top}.bit"
        ).format(
            db_dir = os.path.join(prjxray_db_arg_dir, self._xc7family),
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
        self._run     = kwargs.get("run", True)
        self._check_properties()

        return YosysNextPNRToolchain.build(self, platform, fragment, **kwargs)

    def add_false_path_constraint(self, platform, from_, to):
        # FIXME: false path constraints are currently not supported by the toolchain
        print("WARNING: false path constraints are not supported by the yosys+nextpnr toolchain and are ignored.")
        return


def xilinx_yosys_nextpnr_args(parser):
    toolchain_group = parser.add_argument_group(title="Yosys/NextPNR toolchain options")
    yosys_nextpnr_args(toolchain_group)


def xilinx_yosys_nextpnr_argdict(args):
    return yosys_nextpnr_argdict(args)
