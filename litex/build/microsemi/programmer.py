#
# This file is part of LiteX.
#
# Copyright (c) 2025 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import subprocess

from shutil import which

from litex.build import tools

from litex.build.generic_programmer import GenericProgrammer

# Libero -------------------------------------------------------------------------------------------

class LiberoProgrammer(GenericProgrammer):
    def __init__(self, build_dir, build_name):
        GenericProgrammer.__init__(self)
        self._build_dir  = build_dir
        self._build_name = build_name
        self._impl_path  = os.path.join(self._build_dir, "impl")
        self._prj_path   = os.path.join(self._impl_path, f"{self._build_name}.prjx")

    def load_bitstream(self):
        raise Error("Load bitstream not supported.")

    def flash(self):
        if which("libero") is None:
           msg = "Unable to find or source Libero SoC toolchain, please make sure libero has been installed corectly.\n"
           raise OSError(msg)

        cwd = os.getcwd()
        os.chdir(self._build_dir)

        tcl = [
            f"open_project -file {{{self._prj_path}}} -do_backup_on_convert 1 -backup_file {{{self._impl_path}.zip}}",
            "run_tool -name {PROGRAMDEVICE}",
        ]

        tools.write_to_file(f"{self._build_name}_prog.tcl", "\n".join(tcl))

        libero_cmd = f"libero script:{self._build_name}_prog.tcl"

        if subprocess.call(libero_cmd.split(" ")) != 0:
           raise OSError("Subprocess failed")

        os.chdir(cwd)
