#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import shutil
import subprocess

from litex.build.generic_programmer import GenericProgrammer

# DFUProg ------------------------------------------------------------------------------------------

class DFUProg(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, vid, pid, alt=None):
        self.vid = vid
        self.pid = pid
        self.alt = alt

    def load_bitstream(self, bitstream_file, reset=True):
        dfu_file = bitstream_file + ".dfu"
        shutil.copyfile(bitstream_file, dfu_file)
        subprocess.check_call(["dfu-suffix", "-v", self.vid, "-p", self.pid, "-a", dfu_file])

        flash_cmd = ["dfu-util", "--download", dfu_file]
        if reset:
            flash_cmd.append("-R")
        if self.alt is not None:
            flash_cmd.extend(["-a", str(self.alt)])
        subprocess.check_call(flash_cmd)
