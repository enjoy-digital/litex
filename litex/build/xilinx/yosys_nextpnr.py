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


_openxc7_default_prefix = "/opt/openxc7"

# prjxray and the openXC7 makefiles spell a part as <die><package>-<speedgrade>.
_xc7_part_body = r"xc7(?:[azks][0-9]+[a-z]*|vx[0-9]+[a-z]*)"
_xc7_die_pattern = re.compile(r"^(xc7z007s|xc7z012s|xc7z014s|xc7[azks][0-9]+t?|xc7vx[0-9]+t?)")
_xc7_die_aliases = {
    "xc7a35t" : "xc7a50t",
    "xc7z007s": "xc7z010",
}


def _openxc7_prefix():
    return os.environ.get("NEXTPNR_XILINX_DIR") or _openxc7_default_prefix


def _openxc7_prjxray_db_dir():
    prjxray_db_dir = os.environ.get("PRJXRAY_DB_DIR")
    if prjxray_db_dir:
        return prjxray_db_dir
    prefix = _openxc7_prefix()
    candidates = [
        os.path.join(prefix, "share", "nextpnr", "prjxray-db"),            # toolchain-installer
        os.path.join(prefix, "share", "nextpnr", "external", "prjxray-db"), # toolchain-nix
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0]


def _normalize_xc7_part(device):
    part = device.lower()
    package_last = re.fullmatch(rf"({_xc7_part_body})-([a-z]+[0-9]+)-([0-9][a-z]*)", part)
    if package_last:
        return (
            f"{package_last.group(1)}{package_last.group(2)}-"
            f"{package_last.group(3).upper()}")
    speed_first = re.fullmatch(rf"({_xc7_part_body})-([0-9])([a-z]+[0-9]+)", part)
    if speed_first:
        return f"{speed_first.group(1)}{speed_first.group(3)}-{speed_first.group(2)}"

    # prjxray spells the speed grade's letters uppercase (-2L, -1IL).
    base, separator, speedgrade = part.rpartition("-")
    speedgrade_is_present = re.fullmatch(r"[0-9][a-z]*", speedgrade) is not None
    speedgrade_suffix_is_present = bool(separator) and speedgrade_is_present
    if speedgrade_suffix_is_present:
        return f"{base}-{speedgrade.upper()}"
    return part


def _xc7_part_without_speedgrade(part):
    return re.sub(r"-[0-9][a-z]*$", "", part, flags=re.IGNORECASE)


def _xc7_die(part):
    die = _xc7_die_pattern.match(part)
    if die is None:
        return part
    return _xc7_die_aliases.get(die.group(1), die.group(1))


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
        "v": "virtex7",
        "z": "zynq7"
    }

    @property
    def device(self):
        return  {
            "xc7a35ticsg324-1L": "xc7a35tcsg324-1",
            "xc7a200t-sbg484-1": "xc7a200tsbg484-1",
        }.get(self.platform.device, self.platform.device)

    @property
    def openxc7_part(self):
        return _normalize_xc7_part(self.device)

    @property
    def openxc7_dbpart(self):
        return _xc7_part_without_speedgrade(self.openxc7_part)

    @property
    def openxc7_die(self):
        return _xc7_die(self.openxc7_dbpart)

    def _check_properties(self):
        device = self.platform.device.lower()
        family_match = re.match(r"xc7([akszv])", device)
        if family_match is None:
            raise OSError(f"Unsupported device {self.platform.device}")

        if not self._xc7family:
            family_prefix = family_match.group(1)
            self._xc7family = self.xc7_family_map[family_prefix]

        if not self.dbpart:
            pattern = re.compile(r"xc7([akszv])([0-9]+)(.*)-([0-9])")
            dbpart_match = pattern.search(self.platform.device)
            if dbpart_match is not None:
                self.dbpart = (
                    f"xc7{dbpart_match.group(1)}{dbpart_match.group(2)}{dbpart_match.group(3)}")
            else:
                self.dbpart = self.platform.device

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

    def _openxc7_chipdb_dir(self):
        family_env = self._xc7family.upper() + "_CHIPDB"
        for env_name in ("CHIPDB", family_env):
            chipdb_dir = os.environ.get(env_name)
            if chipdb_dir:
                return chipdb_dir
        return os.path.join(os.getcwd(), "chipdb")

    def _openxc7_bbasm(self):
        bbasm = os.path.join(_openxc7_prefix(), "bin", "bbasm")
        if os.path.exists(bbasm):
            return bbasm
        bbasm = which("bbasm")
        if bbasm is None:
            return "bbasm"
        return bbasm

    def _openxc7_fpga_as(self):
        fpga_as = os.path.join(_openxc7_prefix(), "bin", "fpga-as")
        if os.path.exists(fpga_as):
            return fpga_as
        return which("fpga-as")

    def _ensure_openxc7_chipdb(self, chipdb):
        chipdb_exists = os.path.exists(chipdb)
        if chipdb_exists:
            return

        print(f"Chip database file '{chipdb}' not found, generating...")
        prefix         = _openxc7_prefix()
        prjxray_db_dir = _openxc7_prjxray_db_dir()
        xilinx_gen     = os.path.join(
            prefix, "share", "nextpnr", "himbaechel", "uarch", "xilinx", "gen", "xilinx_gen.py")
        generator_missing = not os.path.exists(xilinx_gen)
        if generator_missing:
            raise OSError(
                f"{xilinx_gen} does not exist; the openXC7 toolchain at '{prefix}' "
                f"has no openXC7/nextpnr chip database generator. Rebuild it from "
                f"https://github.com/openXC7/toolchain-installer, or set CHIPDB to a "
                f"directory containing {self.openxc7_dbpart}.bin."
            )

        xray_family_dir = os.path.join(prjxray_db_dir, self._xc7family)
        database_missing = not os.path.isdir(xray_family_dir)
        if database_missing:
            raise OSError(
                f"{xray_family_dir} does not exist. Set PRJXRAY_DB_DIR to the "
                f"project X-Ray database, or NEXTPNR_XILINX_DIR to the toolchain prefix."
            )

        os.makedirs(os.path.dirname(chipdb), exist_ok=True)
        bba = os.path.splitext(chipdb)[0] + ".bba"
        python3 = os.path.join(prefix, "venv", "bin", "python3")
        if not os.path.exists(python3):
            python3 = which("python3")
            if python3 is None:
                python3 = "python3"

        command = [
            python3, xilinx_gen,
            "--xray",   xray_family_dir,
            "--device", self.openxc7_die,
            "--bba",    bba,
        ]
        print(str(command))
        try:
            result = subprocess.run(command)
            if result.returncode != 0:
                raise OSError(f"Error occured during xilinx_gen.py's execution for '{chipdb}'.")
            result = subprocess.run([self._openxc7_bbasm(), "-l", bba, chipdb])
            if result.returncode != 0:
                raise OSError(f"Error occured during bbasm's execution for '{chipdb}'.")
        finally:
            bba_exists = os.path.exists(bba)
            if bba_exists:
                os.remove(bba)

    def _build_openxc7_bitstream_options(self, prjxray_db_arg_dir):
        db_root = os.path.join(prjxray_db_arg_dir, self._xc7family)
        part    = self.openxc7_part
        fpga_as = self._openxc7_fpga_as()
        fpga_as_available = fpga_as is not None
        if fpga_as_available:
            self._pre_packer_cmd = []
            self.packer_cmd      = fpga_as
            self._packer_opts    = (
                "--prjxray_db_path={db_root} --part {part} {top}.fasm > {top}.bit"
            ).format(
                db_root = db_root,
                part    = part,
                top     = self._build_name
            )
        else:
            self._pre_packer_cmd = ["fasm2frames"]
            self._pre_packer_opts["fasm2frames"] = (
                "--part {part} --db-root {db_root} "
                "{top}.fasm > {top}.frames"
            ).format(
                part    = part,
                db_root = db_root,
                top     = self._build_name
            )
            self.packer_cmd   = "xc7frames2bit"
            self._packer_opts = (
                "--part_file {db_root}/{part}/part.yaml "
                "--part_name {part} "
                "--frm_file {top}.frames "
                "--output_file {top}.bit"
            ).format(
                db_root = db_root,
                part    = part,
                top     = self._build_name
            )

    def finalize(self):
        # toolchain-specific fixes
        for instance in self.fragment.specials:
            if isinstance(instance, Instance):
                self._fix_instance(instance)

        run = getattr(self, "_run", True)

        if self.is_openxc7:
            chipdb_dir         = self._openxc7_chipdb_dir()
            chipdb_arg_dir     = "${CHIPDB:-" + chipdb_dir + "}"
            dbpart             = self.openxc7_dbpart
            chipdb             = os.path.join(chipdb_dir, dbpart) + ".bin"
            chipdb_arg         = os.path.join(chipdb_arg_dir, dbpart) + ".bin"
            prjxray_db_dir     = _openxc7_prjxray_db_dir()
            prjxray_db_arg_dir = "${PRJXRAY_DB_DIR:-" + prjxray_db_dir + "}"
            if run:
                self._ensure_openxc7_chipdb(chipdb)
        else:
            chipdb_dir         = "/usr/share/nextpnr/xilinx-chipdb"
            dbpart             = self.dbpart
            chipdb             = os.path.join(chipdb_dir, dbpart) + ".bin"
            chipdb_arg         = chipdb
            prjxray_db_dir     = "/usr/share/nextpnr/prjxray-db/"
            prjxray_db_arg_dir = prjxray_db_dir
            chipdb_exists = os.path.exists(chipdb)
            chipdb_missing = not chipdb_exists
            chipdb_required = run and chipdb_missing
            if chipdb_required:
                raise OSError(f"Chip database file '{chipdb}' not found. Please check your toolchain installation!")

        # pnr options
        self._pnr_opts += "--chipdb {chipdb} --write {top}_routed.json".format(
            top    = self._build_name,
            chipdb = chipdb_arg
        )

        prjxray_db_exists = os.path.isdir(prjxray_db_dir)
        prjxray_db_missing = not prjxray_db_exists
        prjxray_db_required = run and prjxray_db_missing
        if prjxray_db_required:
            raise OSError(f"{prjxray_db_dir} does not exist on your system. \n" + \
                    "Do you have the openXC7 toolchain installed? \n" + \
                    "You can get it here: https://github.com/openXC7/toolchain-installer")

        if self.is_openxc7:
            self._build_openxc7_bitstream_options(prjxray_db_arg_dir)
        else:
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
